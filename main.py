import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 정밀 수집 시작...")
    
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
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            
            # 사진을 보니 데이터가 많아서 로딩 시간이 필요합니다.
            # 스크롤을 살짝 내려서 아래쪽 데이터까지 깨워줍니다.
            page.mouse.wheel(0, 1000)
            page.wait_for_timeout(7000) 

            # [핵심] 사진 속 작품 카드들의 공통 구조를 타겟팅합니다.
            # 텍스트가 포함된 모든 div를 가져옵니다.
            data_to_push = [["타이틀", "작가", "플랫폼", "조회수", "별점"]]
            
            # 카카오페이지의 작품 리스트는 보통 특정 클래스 묶음으로 되어 있습니다.
            # 모든 작품 제목 요소를 직접 찾습니다.
            items = page.query_selector_all('div.flex-1.cursor-pointer')
            print(f"🔎 발견된 작품 카드 수: {len(items)}개")

            for idx, item in enumerate(items):
                try:
                    # 카드 내부의 텍스트를 줄바꿈으로 나눕니다.
                    lines = [t.strip() for t in item.inner_text().split('\n') if t.strip()]
                    
                    # 사진을 보면 구조가: [순위(있을수도없을수도), 제목] 순서입니다.
                    # 또는 제목만 달랑 있는 경우도 있습니다.
                    if len(lines) >= 1:
                        # 숫자로 시작하면 그 다음 줄이 제목, 아니면 첫 줄이 제목
                        title = lines[1] if lines[0].isdigit() and len(lines) > 1 else lines[0]
                        
                        # 메뉴 이름(웹소설, 웹툰 등)은 제외
                        if title in ["웹소설", "웹툰", "추천", "오늘신작", "랭킹"]:
                            continue
                            
                        # 중복 제거 및 리스트 추가 (조회수/별점은 리스트에 없으므로 일단 제외)
                        if not any(title == row[0] for row in data_to_push):
                            data_to_push.append([title, "작가 정보 확인중", "카카오", "-", "-"])
                except:
                    continue

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push[:21]) # 상위 20개
                print(f"✅ 총 {len(data_to_push)-1}개의 작품 업데이트 완료!")
            else:
                # 정말 실패했을 때를 대비해 페이지 전체를 훑는 최후의 수단
                all_text = page.evaluate("() => document.body.innerText")
                print("❌ 특정 카드를 못 찾아 전체 텍스트에서 제목을 추측합니다.")
                # 이후 로직...
                
        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
