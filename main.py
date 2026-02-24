import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def get_kakao_data(context):
    print("      [1/2] 카카오페이지 수집 중...")
    data = []
    page = context.new_page()
    url = "https://page.kakao.com/menu/10011/screen/94"
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
        unique_links = []
        for l in links:
            if l not in unique_links: unique_links.append(l)
        
        for i, link in enumerate(unique_links[:20]):
            try:
                d_page = context.new_page()
                d_page.goto(link, wait_until="networkidle")
                title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")
                author = d_page.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                
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
    except Exception as e: print(f"❌ 카카오 수집 중단: {e}")
    page.close()
    return data

def get_naver_data(context):
    print("      [2/2] 네이버 시리즈 수집 중...")
    data = []
    page = context.new_page()
    # ⚠️ 네이버 차단 우회를 위해 모바일 버전 주소를 사용해봅니다. (더 가벼움)
    url = "https://m.series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
    
    try:
        page.goto(url, wait_until="load")
        page.wait_for_timeout(5000) # 로딩 대기 시간 대폭 증가

        # 선택자를 더 넓게 잡습니다. (모바일/PC 공용 대응)
        items = page.locator('ul.lst_list > li, div.lst_list_wrap li').all()
        print(f"      🔎 발견된 네이버 작품 수: {len(items)}개")

        for i, item in enumerate(items[:20]):
            try:
                # 제목/작가/링크 추출
                title_link = item.locator('a').first
                title = title_link.inner_text().split('\n')[0].strip()
                href = title_link.get_attribute('href')
                
                author = item.locator('.author, .writer').first.inner_text().strip()
                thumbnail = item.locator('img').first.get_attribute("src")
                
                # 상세페이지 조회수
                detail_url = f"https://series.naver.com{href}" if href.startswith('/') else href
                d_page = context.new_page()
                d_page.goto(detail_url, wait_until="domcontentloaded")
                d_page.wait_for_timeout(2000)
                
                # <span>40.4만</span> 찾기
                views = "-"
                all_text = d_page.evaluate("() => document.body.innerText")
                view_match = re.search(r'(\d+\.?\d*[만|억])', all_text)
                if view_match: views = view_match.group(1)
                
                data.append([f"{i+1}위", "네이버 시리즈", title, author, "장르", views, thumbnail, "2026-02-25"])
                d_page.close()
            except: continue
    except Exception as e: print(f"❌ 네이버 수집 중단: {e}")
    page.close()
    return data

def run_total_ranking():
    print("🚀 통합 랭킹 수집 시작 (카카오 우선 확보)")
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
    except: return

    with sync_playwright() as p:
        # ⚠️ headless=True여도 작동하게끔 설정을 더 정교하게 함
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 14_7_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.2 Mobile/15E148 Safari/604.1",
            viewport={'width': 375, 'height': 812}
        )
        
        kakao_res = get_kakao_data(context)
        naver_res = get_naver_data(context)
        
        # 데이터 합치기
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        final_list = header + kakao_res + naver_res
        
        if len(final_list) > 1: # 데이터가 하나라도 있으면 업데이트
            sh.clear()
            sh.update('A1', final_list)
            print(f"🎊 완료! 카카오({len(kakao_res)}건), 네이버({len(naver_res)}건) 저장됨.")
        else:
            print("⚠️ 수집된 데이터가 없어 시트를 업데이트하지 않았습니다.")
        
        browser.close()

if __name__ == "__main__":
    run_total_ranking()
