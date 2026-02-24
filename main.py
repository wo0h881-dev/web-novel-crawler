import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_crawler():
    # 1. 구글 시트 연결 (가장 안전한 ID 방식)
    creds_json = os.environ['GOOGLE_CREDENTIALS']
    creds = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds)
    
    # 아까 확인하신 시트 주소의 ID를 여기에 넣으세요!
    # 예: https://docs.google.com/spreadsheets/d/12345abcd.../edit 이라면
    # sheet_id = "12345abcd..."
    sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
    sh = gc.open_by_key(sheet_id).sheet1

    # 2. 카카오페이지 크롤링 시작
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # 브라우저처럼 보이기 위한 설정
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        page = context.new_page()
        
        # 카카오페이지 실시간 랭킹 페이지
        url = "https://page.kakao.com/menu/10011/screen/94" 
        page.goto(url)
        page.wait_for_timeout(5000) # 로딩 대기시간 5초로 넉넉히

        # 데이터 추출 (카카오페이지의 최신 구조 반영)
        novels = page.query_selector_all("div.flex-1.cursor-pointer")
        
        data_to_push = []
        # 제목 행 먼저 추가 (원하시는 타이틀 형식)
        data_to_push.append(["타이틀", "작가", "플랫폼", "조회수", "별점"])

        for novel in novels[:20]: # 상위 20개만
            try:
                # 텍스트 추출 시 에러 방지를 위해 하나씩 체크
                title = novel.query_selector(".text-el-70").inner_text()
                author = novel.query_selector(".text-el-60").inner_text()
                data_to_push.append([title, author, "카카오페이지", "-", "-"])
            except:
                continue
        
        # 3. 시트 전체 초기화 후 새로 쓰기
        sh.clear() 
        sh.update('A1', data_to_push)
        print(f"✅ 총 {len(data_to_push)-1}개의 작품 업데이트 완료!")
        
        browser.close()

if __name__ == "__main__":
    run_crawler()
