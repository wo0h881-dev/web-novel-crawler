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

# --- [네이버 수집 함수: 정밀 보정 버전] ---
def get_naver_data(context):
    print("      네이버 시리즈 수집 시작...")
    data = []
    page = context.new_page()
    # 실시간 전체 랭킹 리스트 페이지
    url = "https://series.naver.com/novel/top100List.series?rankingTypeCode=REALTIME&categoryCode=ALL"
    
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # 작품 리스트 아이템 추출
        items = page.locator('ul.lst_list > li').all()
        print(f"      발견된 네이버 작품 수: {len(items)}개")
        
        for i, item in enumerate(items[:20]):
            try:
                # 1. 리스트에서 기본 정보 추출
                title_el = item.locator('h3 > a')
                title = title_el.inner_text().strip()
                author = item.locator('span.author').inner_text().strip()
                thumbnail = item.locator('img').get_attribute("src")
                genre = item.locator('span.genre').inner_text().strip() if item.locator('span.genre').count() > 0 else "-"
                
                # 2. 상세 페이지 주소 추출 및 조립
                href = title_el.get_attribute('href')
                detail_url = f"https://series.naver.com{href}"
                
                # 3. 상세 페이지로 이동하여 조회수 수집
                d_page = context.new_page()
                d_page.goto(detail_url, wait_until="domcontentloaded") # 로딩 속도 최적화
                d_page.wait_for_timeout(2000)
                
                # 조회수 추출 (사용자님이 주신 <span>40.4만</span> 구조 공략)
                views = "-"
                # 상세 페이지 전체에서 '만' 혹은 '억'이 들어간 숫자를 찾습니다.
                content = d_page.content()
                view_match = re.search(r'<span>(\d+\.?\d*[만|억])</span>', content)
                
                if view_match:
                    views = view_match.group(1)
                else:
                    # 만약 위 정규식으로 안 잡힐 경우, 텍스트 전체에서 재검색
                    all_text = d_page.evaluate("() => document.body.innerText")
                    alt_match = re.search(r'(\d+\.?\d*[만|억])', all_text)
                    if alt_match:
                        views = alt_match.group(1)
                
                data.append([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumbnail, "2026-02-25"])
                print(f"      ✅ 네이버 {i+1}위 성공: {title} ({views})")
                d_page.close()
            except Exception as e:
                print(f"      ⚠️ {i+1}위 상세 수집 중 건너뜀: {e}")
                continue
    except Exception as e:
        print(f"❌ 네이버 접속 에러: {e}")
    
    page.close()
    return data

# --- [통합 실행 함수: 카카오 함수가 있다면 여기 합치기] ---
def run_total_ranking():
    print("🚀 통합 랭킹 수집 프로세스 시작...")
    
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
    except Exception as e:
        print(f"❌ 구글 시트 연결 실패: {e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        
        # 1. 네이버 데이터 수집 (카카오가 필요하면 여기에 get_kakao_data(context) 추가)
        naver_results = get_naver_data(context)
        
        # 2. 헤더 및 데이터 병합
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        final_list = header + naver_results # 카카오가 있다면 중간에 추가
        
        # 3. 시트 기록
        sh.clear()
        sh.update('A1', final_list)
        print(f"🎊 완료! 총 {len(naver_results)}개의 네이버 데이터가 반영되었습니다.")
        
        browser.close()

if __name__ == "__main__":
    run_total_ranking()
