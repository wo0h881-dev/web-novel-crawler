import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 상세 데이터(작가/조회수) 수집 시작...")
    
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
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1024},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            
            # 데이터 로딩 대기
            for _ in range(5):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(1500)
            
            # 각 작품 카드(링크)를 가져옵/니다.
            items = page.query_selector_all('a[href*="/content/"]')
            
            # 헤더에 '조회수' 추가
            data_to_push = [["순위", "변동", "타이틀", "작가", "조회수", "수집일"]]
            seen_titles = set()
            rank_counter = 1

            noise_list = ["다크 모드", "Top 300", "설정", "고객센터", "오늘의 PICK"]

            for item in items:
                try:
                    # 카드 내부의 모든 텍스트 추출
                    raw_text = item.inner_text().strip()
                    lines = [t.strip() for t in raw_text.split('\n') if t.strip()]
                    
                    if len(lines) < 1: continue

                    # 1. 제목 찾기 (숫자 아니고 노이즈 아닌 첫 줄)
                    title = ""
                    title_idx = -1
                    for idx, line in enumerate(lines):
                        if len(line) > 1 and not line.isdigit() and line not in noise_list:
                            title = line
                            title_idx = idx
                            break
                    
                    if not title or title in seen_titles: continue

                    # 2. 순위 변동 아이콘
                    change_img = item.query_selector('img[alt="유지"], img[alt="상승"], img[alt="하락"]')
                    change = change_img.get_attribute("alt") if change_img else "-"

                    # 3. 작가명 및 조회수 정밀 추출
                    # 보통 제목(title_idx) 뒤에 [작가명, 조회수] 순으로 옵니다.
                    author = "-"
                    views = "-"
                    
                    if title_idx != -1 and title_idx + 1 < len(lines):
                        author = lines[title_idx + 1]
                        # 만약 다음 줄에 '만뷰'나 '억뷰'가 포함되어 있다면 조회수로 판단
                        if title_idx + 2 < len(lines):
                            next_val = lines[title_idx + 2]
                            if "뷰" in next_val or "만" in next_val:
                                views = next_val

                    data_to_push.append([f"{rank_counter}위", change, title, author, views, "2026-02-24"])
                    seen_titles.add(title)
                    rank_counter += 1
                    
                    if rank_counter > 20: break
                except:
                    continue

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print(f"✅ 작가/조회수 포함 {len(data_to_push)-1}개 업데이트 완료!")
            else:
                print("❌ 데이터를 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 실행 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
