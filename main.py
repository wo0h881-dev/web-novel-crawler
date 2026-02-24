import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 최종 정제 수집 시작...")
    
    # 1. 구글 시트 연결
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        # 본인의 시트 ID를 다시 확인해 주세요!
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
        print("✅ 구글 시트 연결 성공")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        try:
            # 실시간 랭킹 페이지 접속
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            
            # [보정] 충분히 아래까지 로딩되도록 스크롤
            for _ in range(5):
                page.mouse.wheel(0, 1000)
                page.wait_for_timeout(1000)
            
            # 제목 요소(.text-el-60)를 기준으로 전체 덩어리 탐색
            items = page.query_selector_all('div.flex-1.cursor-pointer')
            
            data_to_push = [["순위", "변동", "타이틀", "작가", "수집일"]]
            seen_titles = set()
            rank_counter = 1 # 진짜 소설에만 순위를 붙이기 위한 카운터

            # [노이즈 리스트] 시트 1, 2위에 나왔던 범인들 차단
            noise_list = ["다크 모드", "Top 300", "오늘의 PICK", "설정", "고객센터", "로그아웃", "이벤트", "캐시"]

            for item in items:
                try:
                    # 제목 추출
                    title_el = item.query_selector('.text-el-60')
                    if not title_el: continue
                    title = title_el.inner_text().strip()

                    # 1. 노이즈 필터링 (가짜 제목들 컷)
                    if len(title) < 2 or any(n in title for n in noise_list) or title.isdigit():
                        continue
                    
                    if title not in seen_titles:
                        # 2. 순위 변동 아이콘 추출
                        change_img = item.query_selector('img[alt="유지"], img[alt="상승"], img[alt="하락"]')
                        change = change_img.get_attribute("alt") if change_img else "-"

                        # 3. 작가 정보 추출 (부모 요소 전체 텍스트에서 제목 다음 줄 찾기)
                        full_text = item.inner_text().split('\n')
                        author = "정보 확인중"
                        for i, line in enumerate(full_text):
                            if line.strip() == title and i + 1 < len(full_text):
                                author = full_text[i+1].strip()
                                break

                        # 4. 데이터 적재 (진짜 소설만 여기서 rank_counter가 올라감)
                        data_to_push.append([f"{rank_counter}위", change, title, author, "2026-02-24"])
                        seen_titles.add(title)
                        rank_counter += 1
                        
                except Exception as e:
                    continue
                
                if len(data_to_push) > 21: # 상위 20개만 수집
                    break

            # 3. 시트 저장
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print(f"✅ 축하합니다! {len(data_to_push)-1}개의 소설 리스트가 완벽하게 정제되었습니다.")
            else:
                print("❌ 수집된 데이터가 없습니다. 필터링 조건을 확인해 보세요.")

        except Exception as e:
            print(f"❌ 실행 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
