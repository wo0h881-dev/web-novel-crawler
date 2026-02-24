import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_weekly_rank():
    print("🚀 카카오페이지 [주간 랭킹] 수집 시작...")
    
    # 1. 구글 시트 연결 설정
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        
        # 본인의 시트 ID를 여기에 꼭 넣으세요!
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
        print("✅ 구글 시트 연결 성공")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    # 2. 브라우저 실행 및 크롤링
    with sync_playwright() as p:
        # 브라우저 실행 (가상 환경 최적화)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 주간 랭킹 URL (번호 93)
            url = "https://page.kakao.com/menu/10011/screen/93"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000) # 로딩 대기

            # 작품 카드 찾기
            novels = page.query_selector_all('div[class*="cursor-pointer"]')
            print(f"🔎 발견된 작품 수: {len(novels)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "기타"]] # 헤더

            for novel in novels:
                try:
                    # 칸 안의 모든 텍스트를 가져와 분석
                    raw_text = novel.inner_text().split('\n')
                    # 불필요한 공백 및 숫자(순위) 제거
                    clean_text = [t.strip() for t in raw_text if t.strip() and not t.strip().isdigit()]

                    if len(clean_text) >= 2:
                        title = clean_text[0]  # 첫 번째 줄은 제목
                        author = clean_text[1] # 두 번째 줄은 작가
                        data_to_push.append([title, author, "카카오(주간)", "2026-02-24", "-"])
                except:
                    continue

            # 3. 시트 업데이트 (상위 20개만 저장)
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push[:21]) 
                print(f"✅ 총 {len(data_to_push)-1}개의 주간 랭킹 데이터를 시트에 저장했습니다!")
            else:
                print("❌ 수집된 데이터가 없습니다. 페이지 로딩 상태를 확인해야 합니다.")

        except Exception as e:
            print(f"❌ 크롤링 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_weekly_rank()
