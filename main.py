import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

# --- [카카오 수집 함수] ---
def get_kakao_data(context):
    print("      카카오페이지 수집 중...")
    data = []
    page = context.new_page()
    url = "https://page.kakao.com/menu/10011/screen/94"
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(4000)
        
        links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
        unique_links = []
        for link in links:
            if link not in unique_links: unique_links.append(link)
        
        for i, link in enumerate(unique_links[:20]):
            try:
                d_page = context.new_page()
                d_page.goto(link, wait_until="networkidle")
                d_page.wait_for_timeout(2000)
                
                title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")
                author = d_page.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                
                # 카카오 장르 필터링
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
    except Exception as e:
        print(f"❌ 카카오 에러: {e}")
    page.close()
    return data

# --- [네이버 수집 함수] ---
def get_naver_data(context):
    print("      네이버 시리즈 수집 중...")
    data = []
    page = context.new_page()
    url = "https://series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
    
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # 리스트 아이템 추출
        items = page.locator('ul.lst_list > li').all()
        
        for i, item in enumerate(items[:20]):
            try:
                title = item.locator('h3 > a').inner_text().strip()
                author = item.locator('span.author').inner_text().strip()
                thumbnail = item.locator('img').get_attribute("src")
                genre = item.locator('span.genre').inner_text().strip() if item.locator('span.genre').count() > 0 else "-"
                
                # 네이버 상세페이지 진입 (조회수 수집용)
                detail_url = "https://series.naver.com" + item.locator('h3 > a').get_attribute('href')
                d_page = context.new_page()
                d_page.goto(detail_url, wait_until="networkidle")
                
                # 상세페이지 내 조회수 (예: 40.4만)
                views = "-"
                # '만' 혹은 '억'이 포함된 span을 찾거나 전체 텍스트에서 검색
                all_text = d_page.evaluate("() => document.body.innerText")
                view_match = re.search(r'(\d+\.?\d*[만|억])', all_text)
                if view_match:
                    views = view_match.group(1)
                
                data.append([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumbnail, "2026-02-25"])
                d_page.close()
                print(f"      ✅ 네이버 {i+1}위 완료: {title} ({views})")
            except: continue
    except Exception as e:
        print(f"❌ 네이버 에러: {e}")
    page.close()
    return data

# --- [메인 실행 함수] ---
def run_total_ranking():
    print("🚀 [카카오 x 네이버] 통합 랭킹 수집 시작...")
    
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 시트 ID로 꼭 확인하세요!
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}"); return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        # 1. 카카오 수집
        kakao_data = get_kakao_data(context)
        
        # 2. 네이버 수집
        naver_data = get_naver_data(context)
        
        # 3. 데이터 합치기
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        final_data = header + kakao_data + naver_data
        
        # 4. 시트 업데이트
        sh.clear()
        sh.update('A1', final_data)
        
        print(f"🎊 모든 데이터 수집 완료! (총 {len(final_data)-1}건)")
        browser.close()

if __name__ == "__main__":
    run_total_ranking()
