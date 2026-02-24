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
        
        # 💡 네이버/카카오 차단 회피를 위한 정교한 기기 모사 (iPhone 16 Pro)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 17_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Mobile/15E148 Safari/604.1",
            viewport={'width': 393, 'height': 852},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )

        # --- [STEP 1] 카카오페이지 수집 ---
        print("\n--- [1/2] 카카오페이지 수집 시작 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="load", timeout=60000)
            k_page.wait_for_timeout(5000) # 충분한 로딩 대기
            
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
                    
                    # 장르 추출 로직 복구
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

        # --- [STEP 2] 네이버 시리즈 수집 (모바일 구조 최적화) ---
        print("\n--- [2/2] 네이버 시리즈 수집 시작 ---")
        n_page = context.new_page()
        try:
            # 실시간 랭킹 모바일 주소
            n_url = "https://m.series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
            n_page.goto(n_url, wait_until="networkidle", timeout=60000)
            
            # 💡 중요: 0개가 뜨는 것을 막기 위해 스크롤 및 대기
            n_page.evaluate("window.scrollTo(0, 500)")
            print("   ⏳ 네이버 데이터 로딩 대기 중 (8초)...")
            n_page.wait_for_timeout(8000)

            # 보내주신 HTML의 comic_top_ba 및 일반 리스트 구조 수집
            items = n_page.locator('a.comic_top_ba, .lst_list > li, .lst_list_wrap li').all()
            print(f"   🔎 네이버 발견 항목: {len(items)}개")

            if len(items) == 0:
                print("   ⚠️ 항목 미발견. 페이지 소스를 다시 확인합니다.")

            for i, item in enumerate(items[:20]):
                try:
                    # 1. 제목 (h5.tit 또는 strong)
                    if item.locator('h5.tit').count() > 0:
                        raw_title = item.locator('h5.tit').inner_text()
                        title = raw_title.replace("새로운 에피소드", "").replace("series edition", "").strip()
                    else:
                        title = item.locator('strong').first.inner_text().strip()

                    # 2. 작가 (span.author)
                    author = item.locator('span.author').first.inner_text().strip()

                    # 3. 썸네일
                    thumb_el = item.locator('img').first
                    thumb = thumb_el.get_attribute('src') or thumb_el.get_attribute('data-src')

                    # 4. 상세페이지 조회수
                    href = item.get_attribute('href')
                    if not href:
                        href = item.locator('a').first.get_attribute('href')
                    
                    dp = context.new_page()
                    # 조회수 패턴 매칭을 위해 PC 상세페이지 활용
                    dp.goto(f"https://series.naver.com{href}", wait_until="domcontentloaded")
                    dp_text = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                    
                    # 장르
                    genre = item.locator('.genre').first.inner_text().strip() if item.locator('.genre').count() > 0 else "웹소설"

                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위 완료: {title} ({views})")
                    dp.close()
                    time.sleep(1) # 부하 방지
                except: continue
        except Exception as e:
            print(f"❌ 네이버 에러: {e}")

        browser.close()
        print("\n🎊 모든 수집 프로세스가 종료되었습니다!")

if __name__ == "__main__":
    run_total_ranking()
