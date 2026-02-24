import os
import sys

print("--- 진단 시작 ---")

# 1. 라이브러리 체크
try:
    import playwright
    import gspread
    print("✅ 라이브러리 정상 로드 완료")
except Exception as e:
    print(f"❌ 라이브러리 오류: {e}")
    sys.exit(1)

# 2. 구글 인증 정보 체크
if 'GOOGLE_CREDENTIALS' not in os.environ:
    print("❌ GOOGLE_CREDENTIALS 환경 변수가 없습니다!")
    sys.exit(1)
else:
    print("✅ 환경 변수 감지됨")

print("--- 진단 종료 ---")
