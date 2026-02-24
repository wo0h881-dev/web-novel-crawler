import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 그물망 수집 가동...")
    
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        # 본인의 시트 ID를 다시 한번 확인해주세요!
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
            
            # [보정 1] 데이터를 충분히 불러오기 위해 더 많이, 더 자주 스크롤합니다.
            for _ in range(5):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(1500)
            
            # [보정 2] 제목 요소(.text-el-60)를 먼저 다 찾습니다.
            title_elements = page.query_selector_all('.text-el-60')
            print(f"🔎 발견된 후보 텍스트: {len(title_elements)}개")

            data_to_push = [["순위", "변동", "타이틀", "작가", "수집일"]]
            seen_titles = set()
            rank_counter = 1

            for el in title_elements:
                try:
                    title = el.inner_text().strip()
                    
                    # 노이즈 필터링 (메뉴명, 공지 등 차단)
                    forbidden = ["오늘의 PICK", "TOP 300", "캐시", "선물", "종료", "탭", "번째"]
                    if any(x in title for x in forbidden) or title.isdigit() or len(title) < 2:
                        continue
                    
                    if title not in seen_titles:
                        # 제목의 부모 요소에서 작가 정보와 순위 변동을 유추합니다.
                        # <a> 태그 혹은 감싸는 div 텍스트를 가져옵니다.
                        parent_text = el.evaluate("el => el.closest('a') ? el.closest('a').innerText : ''")
                        lines = [t.strip() for t in parent_text.split('\n') if t.strip()]
                        
                        # 작가 찾기: 보통 제목 아래에 작가명이 있습니다.
                        author = "정보 확인중"
                        for i, line in enumerate(lines):
                            if line == title and i + 1 < len(lines):
                                author = lines[i+1]
                                break
                        
                        # 순위 변동 아이콘 찾기 (부모 안에서 img 찾기)
                        parent_el = el.query_selector("xpath=./ancestor::a")
                        change = "-"
                        if parent_el:
                            img = parent_el.query_selector('img[alt="유지"], img[alt="상승"], img[alt="하락"]')
                            if img: change = img.get_attribute("alt")

                        data_to_push.append([f"{rank_counter}위", change, title, author, "2026-02-24"])
                        seen_titles.add(title)
                        rank_counter += 1
                except:
                    continue
                
                if len(data_to_push) > 21: break

            # 3. 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print(f"✅ 드디어 {len(data_to_push)-1}개 수집 성공! 시트를 확인하세요.")
            else:
                print("❌ 여전히 데이터를 놓쳤습니다. 페이지 구조를 한 번 더 분석해야 합니다.")

        except Exception as e:
            print(f"❌ 실행 중 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
