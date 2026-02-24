import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 정밀 수집 및 정제 시작...")
    
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
            # 실시간 랭킹 페이지 접속
            url = "https://page.kakao.com/menu/10011/screen/94"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            
            # 페이지 로딩 및 리스트 활성화 대기 (스크롤로 데이터 깨우기)
            page.wait_for_timeout(5000)
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(3000)

            # 제목 클래스(.text-el-60)를 타겟팅하여 수집
            title_elements = page.query_selector_all('.text-el-60')
            print(f"🔎 발견된 텍스트 요소: {len(title_elements)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "비고"]]
            seen_titles = set()

            # [노이즈 제거 및 데이터 정제]
            noise_keywords = ["다크 모드", "Top 300", "오늘의 PICK", "설정", "고객센터", "로그아웃", "웹툰", "웹소설", "캐시", "이벤트"]

            for el in title_elements:
                title = el.inner_text().strip()
                
                # 1. 숫자로만 된 것(순위 숫자) 제외
                if title.isdigit():
                    continue
                
                # 2. 너무 짧거나 메뉴 이름인 것 제외
                if len(title) < 2 or any(keyword in title for keyword in noise_keywords):
                    continue
                
                # 3. 중복 제목 제외
                if title not in seen_titles:
                    # 현재 작가 정보 수집 로직은 제외하고 제목 위주로 구성
                    data_to_push.append([title, "카카오 작가", "카카오", "2026-02-24", "-"])
                    seen_titles.add(title)
                
                # 상위 20개만 수집
                if len(data_to_push) > 20:
                    break

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print(f"✅ 총 {len(data_to_push)-1}개의 정제된 작품 저장 완료!")
            else:
                print("❌ 저장할 데이터를 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 크롤링 중 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
