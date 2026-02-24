import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 수집 엔진 가동...")
    
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
            # 실시간 랭킹 주소 (확인하신 메뉴 주소)
            url = "https://page.kakao.com/menu/10011/screen/94"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(10000) # 충분한 로딩 대기

            # [핵심] 모든 '글자' 요소(span)를 다 가져와서 패턴 분석
            # 카카오가 클래스명을 숨겨도 화면에 나오는 글자는 속일 수 없습니다.
            all_spans = page.query_selector_all('span')
            all_texts = [s.inner_text().strip() for s in all_spans if s.inner_text().strip()]
            
            data_to_push = [["타이틀", "작가", "플랫폼", "수집일", "순위"]]
            
            # 패턴 분석: 보통 [순위(숫자), 제목, 작가] 순서로 배열됩니다.
            for i in range(len(all_texts) - 2):
                text = all_texts[i]
                
                # 현재 텍스트가 순위(1~100) 숫자인지 확인
                if text.isdigit() and 1 <= int(text) <= 100:
                    rank = f"{text}위"
                    title = all_texts[i+1]
                    author = all_texts[i+2]
                    
                    # 제목이 메뉴 이름이 아니고, 너무 짧지 않은 경우만 필터링
                    if any(x in title for x in ["탭", "전체", "홈", "랭킹", "이벤트"]):
                        continue
                    
                    if len(title) > 1 and not any(title == row[0] for row in data_to_push):
                        data_to_push.append([title, author, "카카오(실시간)", "2026-02-24", rank])

            # 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                # 순위 순서대로 정렬 (헤더 제외)
                header = data_to_push[0]
                body = sorted(data_to_push[1:], key=lambda x: int(x[4].replace('위','')))
                sh.update('A1', [header] + body[:20]) 
                print(f"✅ 총 {len(body[:20])}개의 실시간 랭킹 데이터 저장 완료!")
            else:
                print("❌ 데이터를 찾지 못했습니다. 구조 분석을 위해 로그를 출력합니다.")
                # 분석용 로그 (상위 30개 텍스트 샘플)
                print(f"텍스트 샘플: {all_texts[:30]}")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
