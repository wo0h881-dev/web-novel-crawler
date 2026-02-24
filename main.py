import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 마지막 승부 수집 시작...")
    
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
        # 실제 사용자처럼 보이게 설정을 더 강화합니다.
        context = browser.new_context(
            viewport={'width': 1280, 'height': 1024},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            print(f"🔗 접속 중: {url}")
            page.goto(url, wait_until="networkidle", timeout=60000)
            
            # [수정 1] 아주 천천히 스크롤하며 데이터가 로드될 시간을 줍니다.
            print("⏳ 데이터 로딩을 위해 스크롤 중...")
            for i in range(5):
                page.mouse.wheel(0, 800)
                page.wait_for_timeout(2000) 

            # [수정 2] 클래스명에만 의존하지 않고, 모든 '작품 링크'를 뒤집니다.
            # 카카오 소설은 항상 /content/ 로 시작하는 링크를 가집니다.
            items = page.query_selector_all('a[href*="/content/"]')
            print(f"🔎 발견된 작품 링크 수: {len(items)}개")

            data_to_push = [["순위", "변동", "타이틀", "작가", "수집일"]]
            seen_titles = set()
            rank_counter = 1

            # 제외할 노이즈 (최소한으로 줄임)
            noise_list = ["다크 모드", "Top 300", "설정", "고객센터"]

            for item in items:
                try:
                    # <a> 태그 안의 텍스트를 몽땅 가져와서 분석
                    raw_text = item.inner_text().strip()
                    lines = [t.strip() for t in raw_text.split('\n') if t.strip()]
                    
                    if len(lines) < 1: continue

                    # 보통 구조: [순위, 제목, 작가, ...] 또는 [제목, 작가, ...]
                    # 제목 후보를 찾습니다.
                    title = ""
                    for line in lines:
                        if len(line) > 1 and not line.isdigit() and line not in noise_list:
                            title = line
                            break
                    
                    if not title or title in seen_titles: continue

                    # 순위 변동 아이콘
                    change_img = item.query_selector('img[alt="유지"], img[alt="상승"], img[alt="하락"]')
                    change = change_img.get_attribute("alt") if change_img else "-"

                    # 작가 정보 (제목 바로 다음 줄인 경우가 많음)
                    author = "정보 확인중"
                    for i, line in enumerate(lines):
                        if line == title and i + 1 < len(lines):
                            author = lines[i+1]
                            break

                    data_to_push.append([f"{rank_counter}위", change, title, author, "2026-02-24"])
                    seen_titles.add(title)
                    rank_counter += 1
                    
                    if rank_counter > 20: break # 20위까지만
                except:
                    continue

            # 3. 시트 업데이트
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print(f"✅ 드디어 성공! {len(data_to_push)-1}개의 작품을 시트에 모셨습니다.")
            else:
                # 실패 시 페이지 텍스트 일부를 출력해서 원인 파악
                print("❌ 여전히 고기가 안 잡히네요. 페이지 텍스트 샘플을 확인합니다.")
                print(page.evaluate("() => document.body.innerText.substring(0, 500)"))

        except Exception as e:
            print(f"❌ 실행 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
