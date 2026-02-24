import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 수집 엔진 가동...")
    
    # [환경 변수 확인]
    if 'GOOGLE_CREDENTIALS' not in os.environ:
        print("❌ 에러: GOOGLE_CREDENTIALS 환경 변수가 설정되지 않았습니다.")
        return

    # [시트 연결]
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        # 본인의 시트 ID를 여기에 꼭 넣으세요!
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
    except Exception as e:
        print(f"❌ 시트 연결 중 에러 발생: {e}")
        return

    # [수집 로직]
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()
        try:
            page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="networkidle")
            page.wait_for_timeout(5000)
            
            # 여기서 에러가 나는지 확인!
            title_elements = page.query_selector_all('.text-el-60')
            print(f"🔎 찾은 제목 수: {len(title_elements)}")
            
            # ... (나머지 코드)
            
        except Exception as e:
            print(f"❌ 수집 중 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
