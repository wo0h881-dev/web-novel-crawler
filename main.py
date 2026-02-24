import os
import json
import gspread
import re
import time
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [통합 랭킹 시스템] 전체 프로세스 시작...")
    
    # 1. 구글 시트 연결 및 초기화
    try:
        creds_raw = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_raw:
            print("❌ 에러: GOOGLE_CREDENTIALS 환경 변수가 없습니다.")
            return
            
        creds = json.loads(creds_raw)
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 시트 ID를 입력하세요
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        # 헤더 작성 및 시트 비우기
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        sh.clear()
        sh.update('A1', header)
        print("✅ 시트 초기화 및 연결 성공")
    except Exception as e:
        print(f"❌ 시작 단계 오류: {e}")
        return

    with sync_playwright() as p:
        # 깃허브 액션 환경을 위한 브라우저 설정
        browser = p.chromium.launch(headless=True)
        # 네이버 차단을 피하기 위한 모바일 유저 에이전트 설정
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
            viewport={'width': 375, 'height': 812}
        )

        # --- [STEP 1] 카카오페이지 수집 ---
        print("\n--- [1/2] 카카오페이지 수집 시작 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="load", timeout=60000)
            k_page.wait_for_timeout(3000) # 리스트 로딩 대기
            
            # 작품 상세 링크 추출
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

                    # 조회수 추출 (정규식)
                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위 완료: {title}")
                    dp.close()
                except: continue
        except Exception as e:
            print(f"❌ 카카오 수집 실패: {e}")
        k_page.close()

        # --- [STEP 2] 네이버 시리즈 수집 (모바일 구조 최적화) ---
        print("\n--- [2/2] 네이버 시리즈 수집 시작 ---")
        n_page = context.new_page()
        try:
            # 실시간 랭킹 모바일 주소
            n_url = "https://m.series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
            n_page.goto(n_url, wait_until="networkidle", timeout=60000)
            
            # 💡 핵심: 0개가 뜨지 않도록 데이터가 로드될 때까지 충분히 대기
            n_page.wait_for_selector("a.comic_top_ba, .lst_list > li", timeout=15000)
            n_page.evaluate("window.scrollTo(0, document.body.scrollHeight/2)")
            time.sleep(2)

            # 보내주신 HTML 구조에 기반한 선택자 적용
            items = n_page.locator('a.comic_top_ba, ul.lst_list > li').all()
            print(f"   🔎 네이버 발견 항목: {len(items)}개")

            for i, item in enumerate(items[:20]):
                try:
                    # 1. 제목 (h5.tit 또는 strong에서 추출)
                    if item.locator('h5.tit').count() > 0:
                        raw_title = item.locator('h5.tit').inner_text()
                        # "새로운 에피소드", "series edition" 등 불필요한 태그 텍스트 제거
                        title = raw_title.replace("새로운 에피소드", "").replace("series edition", "").strip()
                    else:
                        title = item.locator('strong').first.inner_text().strip()

                    # 2. 작가 (span.author)
                    author = item.locator('span.author').first.inner_text().strip()

                    # 3. 썸네일
                    thumb_el = item.locator('img').first
                    thumb = thumb_el.get_attribute('src') or thumb_el.get_attribute('data-src')

                    # 4. 조회수 수집을 위해 상세 페이지 이동
                    href = item.get_attribute('href')
                    if not href:
                        href = item.locator('a').first.get_attribute('href')
                    
                    dp = context.new_page()
                    # 상세페이지는 PC 버전이 텍스트 추출이 더 깔끔함
                    dp.goto(f"https://series.naver.com{href}", wait_until="domcontentloaded")
                    dp_text = dp.evaluate("() => document.body.innerText")
                    views_match = re.search(r'(\d+\.?\d*[만|억])', dp_text)
                    views = views_match.group(1) if views_match else "-"
                    
                    # 장르 (리스트에 있을 경우 가져오고 없으면 상세페이지 분석)
                    genre = item.locator('.genre').first.inner_text().strip() if item.locator('.genre').count() > 0 else "웹소설"

                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위 완료: {title} ({views})")
                    dp.close()
                    
                    time.sleep(0.5) # 서버 부하 방지
                except Exception as e:
                    print(f"   ⚠️ 네이버 {i+1}위 개별 오류: {e}")
                    continue
        except Exception as e:
            print(f"❌ 네이버 수집 실패: {e}")

        browser.close()
        print("\n🎊 모든 작업이 종료되었습니다!")

if __name__ == "__main__":
    run_total_ranking()
