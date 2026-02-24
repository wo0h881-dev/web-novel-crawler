import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [플랫폼 & 썸네일 추가] 수집 시작...")
    
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
            
            # 메인 화면 링크 수집
            links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = []
            for link in links:
                if link not in unique_links: unique_links.append(link)

            # 헤더: 순위, 플랫폼, 타이틀, 작가, 장르, 조회수, 썸네일, 수집일
            data_to_push = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
            
            for i, link in enumerate(unique_links[:20]):
                try:
                    d_page = context.new_page()
                    d_page.goto(link, wait_until="networkidle")
                    d_page.wait_for_timeout(2500)

                    # [1] 타이틀 및 썸네일 (메타데이터 활용)
                    title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                    # 책 표지 이미지 주소 추출
                    thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")
                    
                    # [2] 작가
                    author = "-"
                    author_el = d_page.locator('span.text-el-70.opacity-70').first
                    if author_el.count() > 0:
                        author = author_el.inner_text().strip()
                    
                    # [3] 장르 (필터링 로직)
                    genre = "-"
                    genre_elements = d_page.locator('span.break-all.align-middle').all_inner_texts()
                    if len(genre_elements) > 1:
                        genre = [g for g in genre_elements if g != "웹소설"][0]
                    elif len(genre_elements) == 1:
                        genre = genre_elements[0].replace("웹소설", "").strip()

                    # [4] 조회수
                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만|억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    data_to_push.append([f"{i+1}위", "카카오페이지", title, author, genre, views, thumbnail, "2026-02-25"])
                    print(f"✅ {i+1}위 완료: {title}")
                    d_page.close()
                except:
                    continue

            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 썸네일 주소까지 수집 완료! 웹 제작 준비가 끝났습니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
