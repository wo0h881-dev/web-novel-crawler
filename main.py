import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 최종 수집 및 정제...")
    
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
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)
            page.mouse.wheel(0, 1500) # 리스트 하단까지 로드
            page.wait_for_timeout(3000)

            # [핵심] 개별 작품 카드(덩어리)를 먼저 잡습니다.
            # 이 덩어리 안에 순위, 제목, 작가가 다 들어있습니다.
            items = page.query_selector_all('div.flex-1.cursor-pointer')
            
            data_to_push = [["순위", "변동", "타이틀", "작가", "수집일"]]
            seen_titles = set()

            for item in items:
                try:
                    # 1. 제목 추출 (전달주신 .text-el-60 활용)
                    title_el = item.query_selector('.text-el-60')
                    if not title_el: continue
                    title = title_el.inner_text().strip()

                    # [강력 필터링] 마지막 남은 '오늘의 PICK' 및 노이즈 제거
                    forbidden = ["오늘의 PICK", "TOP 300", "캐시", "선물", "종료 임박"]
                    if any(x in title for x in forbidden) or len(title) < 2:
                        continue

                    # 2. 순위 정보 추출 (숫자로 된 첫 번째 요소)
                    # 3. 순위 변동 아이콘 추출 (img 태그의 alt 속성)
                    all_text = item.inner_text().split('\n')
                    rank = all_text[0] if all_text[0].isdigit() else "-"
                    
                    change_img = item.query_selector('img[alt="유지"], img[alt="상승"], img[alt="하락"]')
                    change = change_img.get_attribute("alt") if change_img else "-"

                    # 4. 작가 정보 추출
                    # 제목 바로 아래에 보통 작가 이름이 위치합니다.
                    # 텍스트 구조상 제목 다음 줄(또는 다다음 줄)을 탐색
                    author = "작가 정보"
                    for i, txt in enumerate(all_text):
                        if txt == title and i+1 < len(all_text):
                            author = all_text[i+1]
                            break

                    if title not in seen_titles:
                        data_to_push.append([f"{rank}위", change, title, author, "2026-02-24"])
                        seen_titles.add(title)
                except:
                    continue

            # 3. 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                # 순위 숫자가 있는 것들만 모아서 정렬 (헤더 제외)
                header = data_to_push[0]
                body = data_to_push[1:]
                # 숫자가 있는 데이터 위주로 20개 자르기
                sh.update('A1', [header] + body[:20])
                print(f"✅ 드디어 완성! 상위 {len(body[:20])}개 작품 저장 완료.")
            else:
                print("❌ 최종 단계에서 데이터를 놓쳤습니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
