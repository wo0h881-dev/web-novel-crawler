import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 리스트 정밀 수집 시작...")
    
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

            # [핵심 보정] 상단 메뉴를 피하기 위해 화면을 아래로 충분히 내립니다.
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(3000)

            # 1. 랭킹 리스트가 시작되는 구역(컨테이너)을 먼저 찾습니다.
            # 보통 'Top 300' 텍스트 이후의 div 섹션에 작품들이 모여있습니다.
            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "비고"]]
            seen_titles = set()

            # 2. 모든 제목 요소를 가져오되, 부모 요소를 확인하여 '리스트 아이템'인 것만 골라냅니다.
            # <a> 태그 안에 있는 제목(.text-el-60)만 가져오는 전략입니다.
            title_elements = page.query_selector_all('a .text-el-60')
            print(f"🔎 후보 제목 요소: {len(title_elements)}개")

            for el in title_elements:
                title = el.inner_text().strip()
                
                # [강력 필터링] 
                # 카테고리 탭에서 흔히 쓰이는 단어와 숫자를 걸러냅니다.
                forbidden = ["탭", "총 16개", "번째", "전체", "TOP", "선택됨"]
                if any(x in title for x in forbidden) or title.isdigit() or len(title) < 2:
                    continue
                
                if title not in seen_titles:
                    data_to_push.append([title, "카카오 작가", "카카오", "2026-02-24", "-"])
                    seen_titles.add(title)
                
                if len(data_to_push) > 20: # 20개만 수집
                    break

            # 3. 데이터 저장
            if len(data_to_push) > 1:
                sh.clear()
                sh.update('A1', data_to_push)
                print(f"✅ '탭' 정보 제외, 총 {len(data_to_push)-1}개의 진짜 제목 저장 완료!")
            else:
                print("❌ 유효한 작품 제목을 찾지 못했습니다.")

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
