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
            page.wait_for_timeout(5000) # 넉넉한 로딩 대기

            # 작품 카드 및 메뉴 탭을 모두 포함하는 요소 탐색
            novels = page.query_selector_all('div[class*="cursor-pointer"]')
            print(f"🔎 탐색된 총 아이템 수: {len(novels)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "비고"]] # 헤더

            for novel in novels:
                try:
                    # 칸 안의 모든 텍스트를 줄바꿈 기준으로 가져옴
                    raw_text = [t.strip() for t in novel.inner_text().split('\n') if t.strip()]
                    
                    # [진짜 소설 판별 로직]
                    # 1. 텍스트가 최소 3줄 이상이어야 함 (순위, 제목, 작가 등)
                    # 2. 첫 번째 줄이 '숫자'(순위)여야 함
                    if len(raw_text) >= 3 and raw_text[0].isdigit():
                        title = raw_text[1]  # 두 번째 줄이 제목
                        author = raw_text[2] # 세 번째 줄이 작가
                        
                        # 메뉴 탭 이름이 제목으로 들어가는 경우 방지
                        if "탭" in title or "전체" in title or "랭킹" in title:
                            continue
                            
                        data_to_push.append([title, author, "카카오(주간)", "2026-02-24", f"{raw_text[0]}위"])
                except:
                    continue

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear() # 기존의 '판타지탭' 같은 오답 데이터 삭제
                sh.update('A1', data_to_push[:21]) # 헤더 포함 상위 20개 저장
                print(f"✅ 총 {len(data_to_push)-1}개의 진짜 소설 데이터를 시트에 저장했습니다!")
            else:
                print("❌ 수집된 소설 데이터가 없습니다. 선택자 로직을 다시 점검해야 합니다.")

        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_weekly_rank()
