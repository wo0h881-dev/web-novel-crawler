import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def get_kakao_data(context):
    print("      카카오페이지 수집 중...")
    data = []
    page = context.new_page()
    url = "https://page.kakao.com/menu/10011/screen/94"
    page.goto(url, wait_until="networkidle")
    page.wait_for_timeout(3000)
    
    links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
    unique_links = []
    for link in links:
        if link not in unique_links: unique_links.append(link)
    
    for i, link in enumerate(unique_links[:20]):
        try:
            d_page = context.new_page()
            d_page.goto(link, wait_until="networkidle")
            d_page.wait_for_timeout(1500)
            title = d_page.locator('meta[property="og:title"]').get_attribute("content")
            thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")
            author = d_page.locator('span.text-el-70.opacity-70').first.inner_text().strip()
            
            # 장르 정제
            genre = "-"
            genre_elements = d_page.locator('span.break-all.align-middle').all_inner_texts()
            if len(genre_elements) > 1:
                genre = [g for g in genre_elements if g != "웹소설"][0]
            elif len(genre_elements) == 1:
                genre = genre_elements[0].replace("웹소설", "").strip()

            view_match = re.search(r'(\d+\.?\d*[만|억])', d_page.evaluate("() => document.body.innerText"))
            views = view_match.group(1) if view_match else "-"
            
            data.append([f"{i+1}위", "카카오페이지", title, author, genre, views, thumbnail, "2026-02-25"])
            d_page.close()
        except: continue
    page.close()
    return data

def get_naver_data(context):
    print("      네이버 시리즈 수집 중...")
    data = []
    page = context.new_page()
    # 네이버 시리즈 실시간 TOP 100 (전체)
    url = "https://series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
    page.goto(url, wait_until="networkidle")
    
    # 네이버는 리스트 페이지에 정보가 꽤 많아 바로 추출 가능합니다.
    items = page.locator('ul.lst_list > li').all()
    
    for i, item in enumerate(items[:20]):
        try:
            # 제목
            title = item.locator('h3 > a').inner_text().strip()
            # 작가 (보통 "작가명" 또는 "작가명 저"로 표시됨)
            author_raw = item.locator('span.author').inner_text().strip()
            author = author_raw.replace("저", "").strip()
            # 장르 (네이버는 리스트에 장르가 표시됨)
            genre = item.locator('span.genre').inner_text().strip()
            # 조회수 대체 (별점 혹은 지수)
            score = item.locator('em.score_num').inner_text().strip()
            views = f"별점 {score}"
            # 썸네일
            thumbnail = item.locator('img').get_attribute("src")
            
            data.append([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumbnail, "2026-02-25"])
        except: continue
    page.close()
    return data

def run_total_ranking():
    print("🚀 [카카오 x 네이버] 통합 랭킹 수집 시작...")
    
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
    except Exception as e:
        print(f"❌ 연결 실패: {e}"); return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        # 데이터 수집
        kakao_list = get_kakao_data(context)
        naver_list = get_naver_data(context)
        
        # 합치기
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        final_data = header + kakao_list + naver_list
        
        # 시트 업데이트
        sh.clear()
        sh.update('A1', final_data)
        print(f"🎊 총 {len(final_data)-1}개의 데이터 업데이트 완료!")
        browser.close()

if __name__ == "__main__":
    run_total_ranking()
