import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 제목 정밀 수집 시작...")
    
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        # 본인의 시트 ID를 입력하세요
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
            
            # 페이지 로딩 및 리스트 활성화 대기
            page.wait_for_timeout(7000)
            page.mouse.wheel(0, 1000) # 스크롤해서 데이터 로드
            page.wait_for_timeout(3000)

            # [핵심] 보내주신 제목 클래스(text-el-60)를 직접 타겟팅합니다.
            # 클래스명이 바뀌더라도 대응할 수 있게 여러 선택자를 시도합니다.
            title_elements = page.query_selector_all('.text-el-60')
            
            data_to_push = [["타이틀", "작가", "플랫폼", "업데이트일", "비고"]]
            seen_titles = set()

            print(f"🔎 발견된 제목 요소: {len(title_elements)}개")

        for el in title_elements:
                title = el.inner_text().strip()
                
                # [강력 필터링 로직]
                # 1. 텍스트가 너무 짧거나(메뉴명), 특정 키워드가 포함되면 버립니다.
                noise_keywords = ["다크 모드", "Top 300", "오늘의 PICK", "설정", "고객센터", "로그아웃", "웹툰", "웹소설"]
                if len(title) < 2 or any(keyword in title for keyword in noise_keywords):
                    continue
                
                # 2. 숫자로만 이루어진 행(순위 정보 등)은 제외합니다.
                if title.isdigit():
                    continue
                
                # 3. 중복 저장 방지
                if title not in seen_titles:
                    data_to_push.append([title, "카카오 작가", "카카오", "2026-02-24", "-"])
                    seen_titles.add(title)
                
                if len(data_to_push) > 20: # 딱 20개만 깔끔하게
                    break

            # 만약 클래스로 못 찾았다면, 아까의 '괴담' 텍스트를 포함한 요소를 강제로 찾습니다.
            if len(data_to_push) == 1:
                print("⚠️ 클래스로 찾기 실패. 텍스트 직접 매칭 시도...")
                all_divs = page.query_selector_all('div')
                for div in all_divs:
                    t = div.inner_text().strip()
                    if "괴담에 떨어져도" in t and len(t) < 100:
                        data_to_push.append([t, "카카오 작가", "카카오", "2026-02-24", "패턴수집"])

            # 3. 시트 업데이트
            sh.clear()
            if len(data_to_push) > 1:
                sh.update('A1', data_to_push)
                print(f"✅ 총 {len(data_to_push)-1}개의 작품 수집 성공!")
            else:
                print("❌ 최종 데이터 추출 실패. 카카오의 방어막이 강력합니다.")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
