import os
import json
import gspread
from playwright.sync_api import sync_playwright

def crawl_kakao_and_update():
    # 1. 구글 시트 연결
    creds_json = os.environ['GOOGLE_CREDENTIALS']
    creds = json.loads(creds_json)
    gc = gspread.service_account_from_dict(creds)
    
    # "웹소설 데이터" 부분에 실제 구글 시트 이름을 적으세요
    sh = gc.open("웹소설 데이터").sheet1

    with sync_playwright() as p:
        # 브라우저 실행
        browser = p.chromium.launch(headless=True)
        page = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36").new_page()
        
        # 카카오페이지 웹소설 랭킹 페이지 접속
        url = "https://page.kakao.com/menu/10011/screen/94" 
        page.goto(url)
        page.wait_for_timeout(3000) # 로딩 대기

        # 데이터 추출 (카카오페이지 구조에 맞춘 선택자)
        novels = page.query_selector_all(".flex-1.cursor-pointer") # 각 소설 아이템
        
        data_to_update = []
        for i, novel in enumerate(novels[:20]): # 상위 20개
            try:
                title = novel.query_selector(".text-el-70").inner_text() # 제목
                author = novel.query_selector(".text-el-60").inner_text() # 작가/정보
                # 조회수는 카카오 구조상 상세페이지에 있어, 메인에서는 '카카오' 플랫폼 명시
                data_to_update.append([title, author, "카카오페이지", "확인필요", 0])
            except:
                continue
        
        # 2. 시트 업데이트 (2행부터 데이터 덮어쓰기)
        if data_to_update:
            sh.update('A2', data_to_update)
            print(f"{len(data_to_update)}개의 데이터를 업데이트했습니다.")
        
        browser.close()

if __name__ == "__main__":
    crawl_kakao_and_update()
