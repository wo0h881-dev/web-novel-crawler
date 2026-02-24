import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [수집 시스템] 가동 시작...")
    
    # 1. 구글 시트 연결
    try:
        creds_raw = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_raw:
            print("❌ 에러: GOOGLE_CREDENTIALS 환경 변수가 없습니다.")
            return
            
        creds = json.loads(creds_raw)
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 시트 ID를 입력하세요
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        sh.clear()
        sh.update('A1', header)
        print("✅ 시트 초기화 완료")
    except Exception as e:
        print(f"❌ 접속 에러: {e}")
        return

    with sync_playwright() as p:
        # 깃허브 액션은 무조건 headless=True
        browser = p.chromium.launch(headless=True)
        # 사람처럼 보이기 위한 브라우저 설정
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
            viewport={'width': 375, 'height': 812}
        )

        # --- [STEP 1] 카카오페이지 수집 ---
        print("\n--- [1/2] 카카오페이지 수집 중 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="load", timeout=60000)
            k_page.wait_for_timeout(3000)
            
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]

            for i, link in enumerate(unique_links):
                try:
                    dp = context.new_page()
                    dp.goto(link, wait_until="load")
                    title = dp.locator('meta[property="og:title"]').get_attribute("content")
                    thumb = dp.locator('meta[property="og:image"]').get_attribute("content")
                    author = dp.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    # ✅ [수정] 카카오 장르 추출 로직
                    genre = "-"
                    g_elements = dp.locator('span.break-all.align-middle').all_inner_texts()
                    if len(g_elements) > 1:
                        genre = [g for g in g_elements if g != "웹소설"][0]
                    elif len(g_elements) == 1:
                        genre = g_elements[0].replace("웹소설", "").strip()

                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위: {title}")
                    dp.close()
                except: continue
        except Exception as e:
            print(f"❌ 카카오 수집 실패: {e}")

        # --- [STEP 2] 네이버 시리즈 수집 (모바일 우회) ---
        print("\n--- [2/2] 네이버 시리즈 수집 중 ---")
        n_page = context.new_page()
        try:
            # 모바일 주소는 PC보다 보안 차단이 덜합니다.
            n_url = "https://m.series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
            n_page.goto(n_url, wait_until="load", timeout=60000)
            n_page.wait_for_timeout(5000)
            
            # 모바일 버전 전용 선택자
            items = n_page.locator('ul.lst_list > li').all()
            print(f"   🔎 네이버 발견 항목: {len(items)}개")

            for i, item in enumerate(items[:20]):
                try:
                    # 모바일 리스트 구조에 맞춘 선택자
                    title_el = item.locator('.info h3, strong').first
                    title = title_el.inner_text().strip()
                    author = item.locator('.author').inner_text().strip()
                    thumb_el = item.locator('img').first
                    thumb = thumb_el.get_attribute('src') or thumb_el.get_attribute('data-src')
                    genre = item.locator('.genre').inner_text().strip() if item.locator('.genre').count() > 0 else "-"

                    # 상세페이지 조회수 (조회수는 PC/모바일 공통 텍스트 패턴 사용)
                    href = item.locator('a').first.get_attribute('href')
                    dp = context.new_page()
                    dp.goto(f"https://series.naver.com{href}", wait_until="domcontentloaded")
                    dp_text = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                    
                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위: {title} ({views})")
                    dp.close()
                except: continue
        except Exception as e:
            print(f"❌ 네이버 수집 실패: {e}")

        browser.close()
        print("\n🎊 모든 수집 프로세스가 종료되었습니다!")

if __name__ == "__main__":
    run_total_ranking()
