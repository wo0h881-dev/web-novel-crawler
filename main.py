import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [순위 고정 + 장르 복구] 수집 시작...")
    
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
            
            # 메인 화면에서 작품 카드들(링크)을 순서대로 수집 (초기 방식)
            items = page.query_selector_all('a[href*="/content/"]')
            
            # 중복 제거 및 상위 20개 링크 추출
            target_links = []
            seen = set()
            for item in items:
                href = page.evaluate("el => el.href", item)
                if href not in seen:
                    target_links.append(href)
                    seen.add(href)
                if len(target_links) >= 20: break

            data_to_push = [["순위", "타이틀", "작가", "장르", "조회수", "수집일"]]
            
            # 이제 수집된 링크를 '순서대로' 방문하며 상세 정보 수집
            for i, link in enumerate(target_links):
                try:
                    detail_page = context.new_page()
                    detail_page.goto(link, wait_until="networkidle")
                    detail_page.wait_for_timeout(2000)

                    # [1] 타이틀 (메타데이터 활용)
                    title = detail_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # [2] 작가 (사용자님이 알려주신 클래스 우선)
                    author = "-"
                    author_el = detail_page.locator('span.text-el-70.opacity-70').first
                    if author_el.count() > 0:
                        author = author_el.inner_text().strip()

                    # [3] 장르 (초기 성공 방식: '웹소설' 포함 텍스트 찾기)
                    genre = "-"
                    all_text_list = detail_page.evaluate("() => Array.from(document.querySelectorAll('span')).map(s => s.innerText)")
                    for text in all_text_list:
                        if "웹소설" in text:
                            genre = text.replace("웹소설", "").replace("·", "").replace(" ", "").strip()
                            break
                    
                    # [4] 조회수
                    body_text = detail_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만|억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    data_to_push.append([f"{i+1}위", title, author, genre, views, "2026-02-24"])
                    print(f"✅ {i+1}위 완료: {title}")
                    
                    detail_page.close()
                except Exception as e:
                    print(f"⚠️ {i+1}위 수집 중 오류: {e}")
                    continue

            # 시트 업데이트
            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 요청하신 대로 순위와 장르 로직을 보정하여 업데이트를 완료했습니다!")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
