import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [순수 장르명 추출] 수집 시작...")
    
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
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
            
            # 메인 화면 링크 수집 (순서 고정)
            items = page.query_selector_all('a[href*="/content/"]')
            target_links = []
            seen = set()
            for item in items:
                href = page.evaluate("el => el.href", item)
                if href and href not in seen:
                    target_links.append(href)
                    seen.add(href)
                if len(target_links) >= 20: break

            data_to_push = [["순위", "타이틀", "작가", "장르", "조회수", "수집일"]]
            
            for i, link in enumerate(target_links):
                try:
                    d_page = context.new_page()
                    d_page.goto(link, wait_until="networkidle")
                    d_page.wait_for_timeout(2500)

                    title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                    author = d_page.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    # [장르 알맹이만 추출]
                    genre = "-"
                    # 부모 요소를 찾아 '웹소설'과 '현판' 텍스트를 한 번에 긁음
                    genre_area = d_page.locator('span:has-text("웹소설")').locator('..')
                    if genre_area.count() > 0:
                        raw_text = genre_area.first.inner_text() 
                        # '웹소설', 줄바꿈(\n), 중간점(·), 공백을 모두 제거
                        # 이렇게 하면 "웹소설 · 현판" -> "현판"만 남습니다.
                        genre = raw_text.replace("웹소설", "").replace("\n", "").replace("·", "").replace(" ", "").strip()
                    
                    # [조회수 추출]
                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만|억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    data_to_push.append([f"{i+1}위", title, author, genre, views, "2026-02-24"])
                    print(f"✅ {i+1}위 완료: {title} ({genre})")
                    d_page.close()
                except:
                    continue

            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 이제 장르 칸에 '현판', '로판'만 깔끔하게 들어갑니다!")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
