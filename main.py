import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [최종 완결판] 수집 시작...")
    
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
        print("✅ 구글 시트 연결 성공")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)
            
            # 스크롤을 여유 있게 해서 모든 카드를 로드합니다.
            for _ in range(3):
                page.mouse.wheel(0, 2000)
                page.wait_for_timeout(2000)

            # [수정] 랭킹 리스트의 '링크'만 먼저 정확히 순서대로 뽑습니다.
            # 이 순서가 곧 실제 실시간 순위입니다.
            links = page.eval_on_selector_all('a[href*="/content/"]', 
                'elements => elements.map(e => e.href)')
            
            # 중복 제거 (카카오 특성상 같은 링크가 두 번 잡힐 수 있음)
            unique_links = []
            for link in links:
                if link not in unique_links:
                    unique_links.append(link)
            
            print(f"🔎 총 {len(unique_links[:20])}개의 작품을 순서대로 분석합니다.")

            data_to_push = [["순위", "타이틀", "작가", "장르", "조회수", "수집일"]]
            
            for i, link in enumerate(unique_links[:20]):
                try:
                    detail_page = context.new_page()
                    detail_page.goto(link, wait_until="networkidle")
                    detail_page.wait_for_timeout(2000)

                    # 1. 타이틀
                    title = detail_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # 2. 작가 (정밀 클래스 타겟팅)
                    author_el = detail_page.locator('span.text-el-70.opacity-70').first
                    author = author_el.inner_text().strip() if author_el.count() > 0 else "-"
                    
                    # 3. 장르 (모든 텍스트에서 '웹소설'이 포함된 span을 찾아 정제)
                    genre = "-"
                    # 페이지 내 모든 span을 검사하여 '웹소설' 단어가 있는 것을 찾음
                    genre_candidates = detail_page.locator('span:has-text("웹소설")').all_inner_texts()
                    if genre_candidates:
                        # 가장 첫 번째 후보에서 정제
                        raw_genre = genre_candidates[0]
                        genre = raw_genre.replace("웹소설", "").replace("·", "").replace(" ", "").strip()
                    
                    # 4. 조회수
                    view_match = re.search(r'(\d+\.?\d*[만|억])', detail_page.evaluate("() => document.body.innerText"))
                    views = view_match.group(1) if view_match else "-"

                    # i+1을 사용하여 화면 순서 그대로 순위를 매깁니다.
                    data_to_push.append([f"{i+1}위", title, author, genre, views, "2026-02-24"])
                    print(f"✅ {i+1}위 수집: {title} | {genre}")
                    
                    detail_page.close()
                except Exception as e:
                    print(f"⚠️ {i+1}위 오류 발생: {e}")
                    continue

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print("🎊 시트 업데이트가 완벽하게 끝났습니다!")
            else:
                print("❌ 수집된 데이터가 없습니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
