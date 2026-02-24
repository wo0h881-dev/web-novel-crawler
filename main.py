import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_weekly_rank():
    print("🚀 카카오페이지 [주간 랭킹] 수집 시작 (보정 버전)...")
    
    # 1. 구글 시트 연결
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

# 2. 크롤링 (텍스트 패턴 매칭 방식)
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 주간 랭킹 페이지 접속
            url = "https://page.kakao.com/menu/10011/screen/93"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            
            # 페이지가 완전히 로드되고 주간 랭킹 탭이 활성화될 때까지 충분히 대기
            page.wait_for_timeout(10000) 

            # 화면 전체에서 모든 텍스트 추출
            all_text = page.evaluate("() => document.body.innerText")
            lines = [l.strip() for l in all_text.split('\n') if l.strip()]
            
            print(f"🔎 추출된 텍스트 라인 수: {len(lines)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "수집일", "순위"]]
            
            # 카카오 랭킹 특유의 패턴 찾기: [순위(숫자), 제목, 작가] 순서로 나타남
            for i in range(len(lines) - 2):
                # 1. 현재 줄이 숫자인지 확인 (1~100위)
                if lines[i].isdigit() and 1 <= int(lines[i]) <= 100:
                    rank = f"{lines[i]}위"
                    title = lines[i+1]
                    author = lines[i+2]
                    
                    # 제목이 메뉴 이름이 아니고 적당한 길이인 경우만 추가
                    if "탭" not in title and "전체" not in title and len(title) > 1:
                        # 중복 방지를 위해 리스트에 없는 경우만 추가
                        if not any(title == row[0] for row in data_to_push):
                            data_to_push.append([title, author, "카카오(주간)", "2026-02-24", rank])

            # 3. 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push[:21]) # 상위 20개만
                print(f"✅ 총 {len(data_to_push)-1}개의 작품을 찾았습니다!")
            else:
                # 실패 시 로그를 더 자세히 남겨서 분석
                print("❌ 유효한 작품 패턴을 찾지 못했습니다.")
                print("--- 텍스트 샘플 (상위 20줄) ---")
                for line in lines[:20]:
                    print(f"[{line}]")

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_weekly_rank()
