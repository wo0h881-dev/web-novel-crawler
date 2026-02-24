import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [숨겨진 데이터] 정밀 수집 시작...")
    
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
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1024},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            
            # 스크롤을 내리며 숨겨진 데이터가 로드되길 기다립니다.
            for _ in range(5):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(2000)
            
            # 작품 카드 <a> 태그 탐색
            items = page.query_selector_all('a[href*="/content/"]')
            
            data_to_push = [["순위", "변동", "타이틀", "작가", "조회수", "수집일"]]
            seen_titles = set()
            rank_counter = 1

            for item in items:
                try:
                    # 1. 제목 찾기
                    title_el = item.query_selector('.text-el-60')
                    if not title_el: continue
                    title = title_el.inner_text().strip()

                    if title in seen_titles or len(title) < 2: continue

                    # 2. [핵심] 숨겨진 텍스트 덩어리 싹 가져오기
                    # 화면에 안 보여도 DOM 구조 안에 텍스트가 있으면 가져옵니다.
                    all_text_content = item.evaluate("el => el.textContent")
                    
                    # 3. 정규표현식이나 키워드로 작가/조회수 추측
                    # 카카오페이지 데이터 패턴: 보통 "작가이름" "조회수" 순서
                    import re
                    
                    # 조회수 패턴: 숫자 + '만' 또는 '억'
                    view_match = re.search(r'(\d+\.?\d*[만|억]뷰?)', all_text_content)
                    views = view_match.group(1) if view_match else "화면표시없음"
                    
                    # 작가 패턴: 제목 뒤에 나오는 첫 번째 의미 있는 단어 (조회수/순위 제외)
                    # 이 부분은 페이지 소스 구조에 따라 "작가"라는 키워드가 숨어있을 수 있습니다.
                    author = "분석중"
                    info_parts = item.inner_text().split('\n')
                    for p_text in info_parts:
                        p_text = p_text.strip()
                        if p_text and p_text != title and not p_text.isdigit() and "뷰" not in p_text:
                            if p_text not in ["상승", "하락", "유지", "신작", "UP"]:
                                author = p_text
                                break

                    # 4. 순위 변동
                    change_img = item.query_selector('img[alt="유지"], img[alt="상승"], img[alt="하락"]')
                    change = change_img.get_attribute("alt") if change_img else "-"

                    data_to_push.append([f"{rank_counter}위", change, title, author, views, "2026-02-24"])
                    seen_titles.add(title)
                    rank_counter += 1
                    
                    if rank_counter > 20: break
                except:
                    continue

            # 3. 시트 업데이트
            sh.clear()
            sh.update('A1', data_to_push)
            print(f"✅ 수집 완료! (일부 정보는 페이지 구조상 상세페이지 진입이 필요할 수 있습니다.)")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
