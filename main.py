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
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/93"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(7000) # 로딩 시간을 7초로 더 늘렸습니다.

            # 작품 아이템 추출
            items = page.query_selector_all('div[class*="cursor-pointer"]')
            print(f"🔎 탐색된 총 아이템 수: {len(items)}개")

            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "비고"]]

            for item in items:
                try:
                    # 텍스트를 일단 다 긁어옵니다.
                    text_content = item.inner_text().strip()
                    if not text_content: continue
                    
                    lines = [t.strip() for t in text_content.split('\n') if t.strip()]
                    
                    # [필터링 완화 로직]
                    # 메뉴 탭(판타지탭 등)은 텍스트에 '탭'이 들어가거나 매우 짧습니다.
                    if any(x in text_content for x in ["탭", "전체", "실시간", "랭킹", "오늘신작"]):
                        continue
                    
                    # 진짜 소설은 보통 [순위, 제목, 작가, 조회수/별점] 순서입니다.
                    # 순위 숫자가 맨 앞에 있거나 제목 뒤에 붙어있을 수 있습니다.
                    if len(lines) >= 2:
                        # 첫 번째가 숫자면 1위 제목 2위 작가 순
                        if lines[0].isdigit():
                            title = lines[1]
                            author = lines[2] if len(lines) > 2 else "정보없음"
                            rank = f"{lines[0]}위"
                        else:
                            # 숫자가 없더라도 제목과 작가로 추정되는 것들을 가져옵니다.
                            title = lines[0]
                            author = lines[1]
                            rank = "-"
                        
                        # 중복 방지 및 제목 길이 체크 (너무 짧은 메뉴 이름 방어)
                        if len(title) > 1:
                            data_to_push.append([title, author, "카카오(주간)", "2026-02-24", rank])
                except:
                    continue

            # 3. 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                # 중복 데이터 제거 (제목 기준)
                seen = set()
                final_data = []
                for row in data_to_push:
                    if row[0] not in seen:
                        final_data.append(row)
                        seen.add(row[0])
                
                sh.update('A1', final_data[:21]) 
                print(f"✅ 총 {len(final_data)-1}개의 주간 랭킹 소설 저장 완료!")
            else:
                print("❌ 여전히 데이터를 찾지 못했습니다. 구조 확인이 필요합니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_weekly_rank()
