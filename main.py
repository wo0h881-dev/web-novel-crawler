import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_rank():
    print("🚀 카카오페이지 랭킹 수집 시작...")
    
    # 1. 구글 시트 연결
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        
        # 본인의 시트 ID를 넣어주세요 (주소창 /d/와 /edit 사이의 문자열)
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
        print("✅ 구글 시트 연결 성공")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    # 2. 카카오페이지 크롤링
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 카카오페이지 웹소설 실시간 랭킹
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000) # 충분한 로딩 대기

            # 작품 아이템들을 더 넓은 범위로 탐색
            novels = page.query_selector_all('div[class*="cursor-pointer"]')
            print(f"🔎 발견된 아이템 수: {len(novels)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "조회수", "별점"]] # 헤더

            for novel in novels:
                try:
                    # 제목과 작가가 포함된 텍스트 영역 찾기
                    title_element = novel.query_selector(".text-el-70") # 제목 클래스
                    author_element = novel.query_selector(".text-el-60") # 작가 클래스
                    
                    if title_element:
                        title = title_element.inner_text().strip()
                        author = author_element.inner_text().strip() if author_element else "작가 미상"
                        data_to_push.append([title, author, "카카오페이지", "-", "-"])
                except:
                    continue

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push[:21]) # 상위 20개만
                print(f"✅ {len(data_to_push)-1}개의 데이터를 시트에 저장했습니다!")
            else:
                print("❌ 수집된 데이터가 없습니다. 선택자를 확인해야 합니다.")

        except Exception as e:
            print(f"❌ 크롤링 중 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_rank()
