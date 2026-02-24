import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_rank():
    print("🚀 카카오페이지 데이터 정밀 수집 시작...")
    
    # 1. 구글 시트 연결
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
            # 주간 랭킹(93) 또는 실시간(94) 중 원하는 URL 사용
            url = "https://page.kakao.com/menu/10011/screen/93"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(8000) # 로딩 대기

            # [핵심] <a> 태그이면서 내부에 이미지가 있고, 텍스트가 있는 요소만 추출
            # 광고 배너는 보통 <a> 구조가 소설과 다르다는 점을 이용합니다.
            cards = page.query_selector_all('div.flex-1.cursor-pointer')
            print(f"🔎 후보 아이템 수: {len(cards)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "수집일", "순위"]]
            
            for card in cards:
                try:
                    # 칸 안의 텍스트 추출
                    raw_text = [t.strip() for t in card.inner_text().split('\n') if t.strip()]
                    
                    # 진짜 소설은 보통 [순위, 제목, 작가, (기타정보)] 순서로 3줄 이상입니다.
                    if len(raw_text) >= 3 and raw_text[0].isdigit():
                        rank_num = int(raw_text[0])
                        title = raw_text[1]
                        author = raw_text[2]
                        
                        # 광고성 키워드 차단 (이중 보안)
                        if any(x in title for x in ["캐시", "이벤트", "선물", "선공개"]):
                            continue
                        
                        # 중복 제거 및 리스트 추가
                        if not any(title == row[0] for row in data_to_push):
                            data_to_push.append([title, author, "카카오(주간)", "2026-02-24", f"{rank_num}위"])
                except:
                    continue

            # 3. 데이터 저장 (순위순 정렬)
            if len(data_to_push) > 1:
                header = data_to_push[0]
                # 순위 숫자로 정렬
                body = sorted(data_to_push[1:], key=lambda x: int(x[4].replace('위','')))
                
                sh.clear()
                sh.update('A1', [header] + body[:20]) # 상위 20개
                print(f"✅ 총 {len(body[:20])}개의 작품 저장 성공!")
            else:
                print("❌ 유효한 소설 목록을 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_rank()
