import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_weekly_rank():
    print("🚀 카카오페이지 [주간 랭킹] 진짜 목록 수집 시작...")
    
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
            url = "https://page.kakao.com/menu/10011/screen/93"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(8000) 

            # [핵심 수정] 상단 배너를 제외하고 실제 '리스트'가 담긴 영역의 아이템만 찾습니다.
            # 카카오 리스트 아이템들은 보통 특정 구조 안에 묶여 있습니다.
            items = page.query_selector_all('div[class*="cursor-pointer"]')
            
            data_to_push = [["타이틀", "작가", "플랫폼", "수집일", "순위"]]
            
            for item in items:
                try:
                    raw_text = [t.strip() for t in item.inner_text().split('\n') if t.strip()]
                    
                    # 소설 아이템 판별 기준 강화:
                    # 1. 광고 문구에 자주 쓰이는 단어 제외
                    # 2. 텍스트가 너무 길거나 짧은 배너 형태 제외
                    full_text = "".join(raw_text)
                    if any(x in full_text for x in ["선공개", "캐시", "선물", "이벤트", "탭"]):
                        continue
                    
                    # 진짜 랭킹 아이템은 [순위, 제목, 작가, 조회수...] 순서입니다.
                    if len(raw_text) >= 3 and raw_text[0].isdigit():
                        rank_num = int(raw_text[0])
                        # 1위부터 100위 사이의 숫자만 인정 (광고의 14 같은 숫자 방어)
                        if 1 <= rank_num <= 100:
                            title = raw_text[1]
                            author = raw_text[2]
                            
                            # 중복 체크
                            if not any(title == row[0] for row in data_to_push):
                                data_to_push.append([title, author, "카카오(주간)", "2026-02-24", f"{rank_num}위"])
                except:
                    continue

            # 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                # 순위별로 정렬해서 넣기
                header = data_to_push[0]
                body = sorted(data_to_push[1:], key=lambda x: int(x[4].replace('위','')))
                sh.update('A1', [header] + body[:20]) 
                print(f"✅ 총 {len(body[:20])}개의 소설을 순위대로 저장했습니다!")
            else:
                print("❌ 진짜 소설 목록을 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_weekly_rank()
