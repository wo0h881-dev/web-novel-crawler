import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [진단 시작] 프로세스를 가동합니다...")
    
    # 1. 시트 접속 단계 진단
    try:
        creds_raw = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_raw:
            print("❌ 에러: GOOGLE_CREDENTIALS 환경 변수가 없습니다.")
            return
            
        creds = json.loads(creds_raw)
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 시트 ID가 맞는지 다시 확인!
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        print("✅ 구글 시트 연결 성공")
    except Exception as e:
        print(f"❌ 시트 접속 단계 에러: {e}")
        return

    # 초기화
    header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
    sh.clear()
    sh.update('A1', header)

    with sync_playwright() as p:
        print("🌐 브라우저 실행 중...")
        # 💡 아무 반응이 없을 땐 headless=False로 바꿔서 창이 뜨는지 봐야 합니다.
        browser = p.chromium.launch(headless=False) 
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # --- [카카오] ---
        print("--- [카카오] 수집 시작 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="load", timeout=30000)
            k_page.wait_for_timeout(3000)
            
            # 카카오 리스트 추출
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]
            print(f"   카카오 작품 {len(unique_links)}개 발견")

            for i, link in enumerate(unique_links):
                dp = context.new_page()
                dp.goto(link, wait_until="load")
                title = dp.locator('meta[property="og:title"]').get_attribute("content")
                author = dp.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                thumb = dp.locator('meta[property="og:image"]').get_attribute("content")
                
                # 장르 복구 로직
                genre = "-"
                g_elements = dp.locator('span.break-all.align-middle').all_inner_texts()
                genre = [g for g in g_elements if g != "웹소설"][0] if len(g_elements) > 1 else "-"

                body = dp.evaluate("() => document.body.innerText")
                views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                
                sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                print(f"   ✅ 카카오 {i+1}위 기록: {title}")
                dp.close()
        except Exception as e:
            print(f"❌ 카카오 과정 중 상세 에러: {e}")

        # --- [네이버] ---
        print("\n--- [네이버] 수집 시작 ---")
        n_page = context.new_page()
        try:
            # 주소 뒤에 파라미터를 붙여 실시간 랭킹을 강제로 호출
            n_url = "https://series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
            n_page.goto(n_url, wait_until="load", timeout=30000)
            n_page.wait_for_timeout(5000)

            # 네이버 차단 확인용 스크린샷 (선택 사항)
            # n_page.screenshot(path="naver_check.png") 

            # 선택자 대폭 보강: 주신 HTML의 'comic_cont' 클래스를 직접 타겟팅
            items = n_page.locator('.lst_list_wrap li, .lst_list li').all()
            print(f"   🔎 네이버 리스트 로드 결과: {len(items)}개 발견")

            for i, item in enumerate(items[:20]):
                try:
                    # h3 내부의 a 태그 찾기
                    target_a = item.locator('h3 a').first
                    title = target_a.inner_text().strip()
                    href = target_a.get_attribute('href')
                    author = item.locator('.author').first.inner_text().strip()
                    thumb = item.locator('img').first.get_attribute('src')
                    genre = item.locator('.genre').first.inner_text().strip() if item.locator('.genre').count() > 0 else "-"

                    # 상세페이지 이동
                    dp = context.new_page()
                    dp.goto(f"https://series.naver.com{href}", wait_until="load")
                    dp_text = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                    
                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위 기록: {title}")
                    dp.close()
                except Exception as e:
                    print(f"   ⚠️ 네이버 {i+1}위 개별 수집 실패")
                    continue
        except Exception as e:
            print(f"❌ 네이버 과정 중 상세 에러: {e}")

        browser.close()
        print("\n🎊 모든 프로세스 종료")

if __name__ == "__main__":
    run_total_ranking()
