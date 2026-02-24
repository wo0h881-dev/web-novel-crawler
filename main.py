import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [완전 재설정] 수집 시작...")
    
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
        # 브라우저 실행 시 캐시 제거를 위해 context를 매번 새로 생성
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        try:
            page = context.new_page()
            url = "https://page.kakao.com/menu/10011/screen/94"
            # 캐시를 무시하고 페이지 로드
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)
            
            # 메인 리스트 <a> 태그들
            items = page.query_selector_all('a[href*="/content/"]')
            
            # 링크 수집 (중복 제거하되 순서는 유지)
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
                    # 매번 새 페이지를 열어 캐시 오염 방지
                    d_page = context.new_page()
                    d_page.goto(link, wait_until="networkidle")
                    d_page.wait_for_timeout(2000)

                    # [1] 타이틀
                    title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # [2] 작가 (상세 페이지에서 클래스로 추출)
                    author = d_page.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    # [3] 장르 (강력한 정제: 웹소설이 포함된 태그의 텍스트에서 '웹소설' 제거)
                    genre = "-"
                    spans = d_page.locator('span').all_inner_texts()
                    for s in spans:
                        if "웹소설" in s:
                            genre = s.replace("웹소설", "").strip()
                            break
                    
                    # [4] 조회수
                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만|억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    data_to_push.append([f"{i+1}위", title, author, genre, views, "2026-02-24"])
                    print(f"✅ {i+1}위 수집: {title}")
                    d_page.close()
                except:
                    continue

            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 이번엔 정말 되었을 겁니다! 시트를 확인해 보세요.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
