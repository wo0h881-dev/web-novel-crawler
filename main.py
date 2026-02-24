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

 # 2. 크롤링
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 실제 사용자처럼 보이기 위한 정밀 설정
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 1024}
        )
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/93"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(8000) # 로딩 대기 시간을 8초로 충분히 확보

            # 작품 아이템 추출 (더 넓은 범위의 선택자 사용)
            items = page.query_selector_all('div[class*="cursor-pointer"]')
            print(f"🔎 탐색된 총 아이템 수: {len(items)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "비고"]]

            for item in items:
                try:
                    # 해당 칸 안의 모든 span 태그(글자들)를 가져옵니다.
                    spans = item.query_selector_all('span')
                    texts = [s.inner_text().strip() for s in spans if s.inner_text().strip()]
                    
                    # 메뉴 탭 필터링 (텍스트에 '탭'이 들어있으면 제외)
                    total_text = "".join(texts)
                    if any(x in total_text for x in ["탭", "실시간", "오늘신작", "장르"]):
                        continue

                    # 카카오 주간 랭킹의 전형적인 구조: [순위, 제목, 작가, 조회수/별점...]
                    if len(texts) >= 3:
                        # 첫 번째가 숫자(순위)인 경우
                        if texts[0].isdigit():
                            rank = f"{texts[0]}위"
                            title = texts[1]
                            author = texts[2]
                        else:
                            # 숫자가 없더라도 첫 두 요소를 제목과 작가로 간주
                            rank = "-"
                            title = texts[0]
                            author = texts[1]

                        # 제목이 너무 짧은 노이즈 제거
                        if len(title) > 1:
                            data_to_push.append([title, author, "카카오(주간)", "2026-02-24", rank])
                except:
                    continue

            # 3. 데이터 저장 및 중복 제거
            if len(data_to_push) > 1:
                sh.clear()
                # 제목 기준 중복 제거
                seen = set()
                final_data = []
                for row in data_to_push:
                    if row[0] not in seen:
                        final_data.append(row)
                        seen.add(row[0])
                
                sh.update('A1', final_data[:21]) 
                print(f"✅ 총 {len(final_data)-1}개의 주간 랭킹 소설 저장 완료!")
            else:
                # 만약 위 방법도 실패하면, 페이지 전체 텍스트 구조를 로그에 찍어 확인합니다.
                print("❌ 데이터를 찾지 못했습니다. 현재 페이지의 텍스트 일부를 분석합니다:")
                sample = page.content()[:500]
                print(f"샘플 HTML: {sample}")

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_weekly_rank()
