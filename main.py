import os
import json
import gspread
import re
import time
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [최종 통합 시스템] 수집을 시작합니다...")
    
    # 1. 구글 시트 연결 환경 설정
    try:
        creds_raw = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_raw:
            print("❌ 에러: GOOGLE_CREDENTIALS 환경 변수가 없습니다.")
            return
            
        creds = json.loads(creds_raw)
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 구글 시트 ID를 입력하세요
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        # 헤더 초기화
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        sh.clear()
        sh.update('A1', header)
        print("✅ 구글 시트 초기화 완료")
    except Exception as e:
        print(f"❌ 시트 연결 에러: {e}")
        return

    with sync_playwright() as p:
        # 브라우저 실행
        browser = p.chromium.launch(headless=True)
        
        # 💡 네이버 차단 회피를 위해 일반 윈도우 PC 크롬 브라우저로 위장
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )

        # --- [STEP 1] 카카오페이지 수집 ---
        print("\n--- [1/2] 카카오페이지 수집 시작 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="load", timeout=60000)
            k_page.wait_for_timeout(3000)
            
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]
            print(f"   🔎 카카오 작품 {len(unique_links)}개 발견")

            for i, link in enumerate(unique_links):
                try:
                    dp = context.new_page()
                    dp.goto(link, wait_until="load")
                    title = dp.locator('meta[property="og:title"]').get_attribute("content")
                    thumb = dp.locator('meta[property="og:image"]').get_attribute("content")
                    author = dp.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    # 장르 추출 로직
                    genre = "-"
                    g_elements = dp.locator('span.break-all.align-middle').all_inner_texts()
                    if len(g_elements) > 1:
                        genre = [g for g in g_elements if g != "웹소설"][0]
                    elif len(g_elements) == 1:
                        genre = g_elements[0].replace("웹소설", "").strip()

                    # 조회수 추출
                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위 완료: {title}")
                    dp.close()
                except: continue
        except Exception as e:
            print(f"❌ 카카오 에러: {e}")
        k_page.close()

        # --- [STEP 2] 네이버 시리즈 수집 (차단 방지 보강) ---
        print("\n--- [2/2] 네이버 시리즈 수집 시작 ---")
        n_page = context.new_page()
        try:
            # 주소를 PC 버전 랭킹으로 먼저 시도 (해외 IP 차단 회피용)
            n_url = "https://series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
            n_page.goto(n_url, wait_until="networkidle", timeout=60000)
            
            # 💡 인위적인 스크롤 및 긴 대기 시간으로 봇 감지 회피
            n_page.evaluate("window.scrollTo(0, 800)")
            print("   ⏳ 네이버 응답 대기 중 (10초)...")
            n_page.wait_for_timeout(10000)

            # PC 버전 리스트 선택자 시도
            items = n_page.locator('ul.lst_list > li, div.lst_list_wrap li').all()
            
            # 만약 PC 버전 실패 시 모바일 버전으로 재시도
            if len(items) == 0:
                print("   ⚠️ PC 버전 0개 발견, 모바일 우회 접속 시도...")
                n_page.goto("https://m.series.naver.com/novel/top100List.series", wait_until="networkidle")
                n_page.wait_for_timeout(7000)
                items = n_page.locator('a.comic_top_ba, ul.lst_list > li').all()

            print(f"   🔎 네이버 최종 발견 항목: {len(items)}개")

            for i, item in enumerate(items[:20]):
                try:
                    # 제목 추출 (다중 선택자 대응)
                    title_el = item.locator('h3 a, dt a, h5.tit, .tit, strong').first
                    title = title_el.inner_text().replace("새로운 에피소드", "").replace("series edition", "").strip()
                    
                    # 작가 추출
                    author = item.locator('.author, .wt, span.author').first.inner_text().strip()
                    
                    # 썸네일
                    thumb_el = item.locator('img').first
                    thumb = thumb_el.get_attribute('src') or thumb_el.get_attribute('data-src')

                    # 상세페이지 조회수 수집
                    href = title_el.get_attribute('href') if title_el.get_attribute('href') else item.locator('a').first.get_attribute('href')
                    full_href = href if href.startswith('http') else f"https://series.naver.com{href}"
                    
                    dp = context.new_page()
                    dp.goto(full_href, wait_until="domcontentloaded")
                    dp_text = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                    
                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, "웹소설", views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위 완료: {title} ({views})")
                    dp.close()
                    time.sleep(1) 
                except: continue
        except Exception as e:
            print(f"❌ 네이버 최종 에러: {e}")

        browser.close()
        print("\n🎊 모든 수집 프로세스가 성공적으로 종료되었습니다!")

if __name__ == "__main__":
    run_total_ranking()
