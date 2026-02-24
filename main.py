import os
import json
import gspread

def run_test():
    print("--- 시스템 점검 시작 ---")
    try:
        # 1. Secrets 확인
        print("1. Secrets 로드 중...")
        creds_json = os.environ.get('GOOGLE_CREDENTIALS')
        if not creds_json:
            print("❌ 에러: GOOGLE_CREDENTIALS 시크릿을 찾을 수 없습니다.")
            return
        
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        print("✅ 구글 인증 성공!")

        # 2. 시트 열기
        sheet_name = "웹소설 데이터" # <-- 여기를 실제 시트 이름으로 수정!!
        print(f"2. '{sheet_name}' 시트 여는 중...")
        sh = gc.open(sheet_name).sheet1
        print("✅ 시트 찾기 성공!")

        # 3. 데이터 쓰기
        sh.update('A1', [['마지막 확인 시간', '상태'], ['2026-02-24', '연결됨']])
        print("✅ 데이터 쓰기 성공! 이제 구글 시트를 확인해 보세요.")

    except gspread.exceptions.SpreadsheetNotFound:
        print(f"❌ 에러: '{sheet_name}'이라는 이름의 시트를 찾을 수 없습니다.")
    except Exception as e:
        print(f"❌ 기타 에러 발생: {e}")

if __name__ == "__main__":
    run_test()
