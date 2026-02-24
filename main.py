import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

# --- [1. 카카오페이지 수집 함수] ---
def get_kakao_data(context):
    print("      [1/2] 카카오페이지 수집 시작...")
    data = []
    page = context.new_page()
    url = "https://page.kakao.com/menu/10011/screen/94"
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(3000)
        
        # 상세 페이지 링크 추출
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
                
                # 장르 필터링
                genre_elements = d_page.locator('span.break-all.align-middle').all_inner_texts()
                genre = [g for g in genre_elements if g != "웹소설"][0] if len(genre_elements) > 1 else "-"

                # 조회수 (만/억 단위 추출)
                view_match = re.search(r'(\d+\.?\d*[만|억])', d_page.evaluate("() => document.body.innerText"))
                views = view_match.group(1) if view_match else "-"
                
                data.append([f"{i+1}위", "카카오페이지", title, author, genre, views, thumbnail, "2026-02-25"])
                d_page.close()
                print(f"      ✅ 카카오 {i+1}위 완료: {title}")
            except: continue
    except Exception as e:
        print(f"      ❌ 카카오 수집 중 에러: {e}")
    page.close()
    return data

# --- [2. 네이버 시리즈 수집 함수] ---
def get_naver_data(context):
    print("      [2/2] 네이버 시리즈 수집 시작...")
    data = []
    page = context.new_page()
    url = "https://series.naver.com/novel/top100List.series"
    
    try:
        page.goto(url, wait_until="networkidle")
        page.wait_for_timeout(4000)

        # 사용자님이 주신 HTML 구조 기반 선택자 (li 태그 20개 추출)
        items = page.locator('div.lst_list_wrap > ul > li, ul.lst_list > li').all()
        print(f"      🔎 발견된 네이버 작품 수: {len(items)}개")

        for i, item in enumerate(items[:20]):
            try:
                # 1. 리스트 페이지 기본 정보
                title_el = item.locator('div.comic_cont h3 a')
                title = title_el.inner_text().strip()
                href = title_el.get_attribute('href')
                author = item.locator('span.author').inner_text().strip()
                thumbnail = item.locator('a.pic img').get_attribute('src')
                genre = item.locator('span.genre').inner_text().strip() if item.locator('span.genre').count() > 0 else "-"
                
                # 2. 상세 페이지 접속 (조회수 수집용)
                detail_url = f"https://series.naver.com{href}"
                d_page = context.new_page()
                d_page.goto(detail_url, wait_until="domcontentloaded")
                d_page.wait_for_timeout(1500)
                
                # 상세 페이지 내 40.4만 같은 텍스트 패턴 추출
                body_text = d_page.evaluate("() => document.body.innerText")
                view_match = re.search(r'(\d+\.?\d*[만|억])', body_text)
                views = view_match.group(1) if view_match else "-"
                
                data.append([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumbnail, "2026-02-25"])
                print(f"      ✅ 네이버 {i+1}위 완료: {title} ({views})")
                d_page.close()
            except: continue
    except Exception as e:
        print(f"      ❌ 네이버 수집 중 에러: {e}")
    page.close()
    return data

# --- [3. 통합 실행 및 시트 업데이트] ---
# 상단에 이 라이브러리가 필요할 수 있습니다 (설치 안 되어 있다면: pip install playwright-stealth)
# 만약 설치가 번거로우시면 아래의 'context' 설정만 잘 따라와주세요.

def run_total_ranking():
    print("🚀 [통합 랭킹 시스템] 전체 프로세스 시작...")
    
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    with sync_playwright() as p:
        # 1. 브라우저 실행 시 봇 감지 우회 옵션 추가
        browser = p.chromium.launch(headless=True) # 여전히 0개면 False로 바꿔보세요!
        
        # 2. 컨텍스트 설정 (화면 크기, 언어, 유저에이전트를 실제 사람처럼 설정)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale="ko-KR",
            timezone_id="Asia/Seoul"
        )
        
        # 3. 자동화 흔적 제거 스크립트 실행 (네이버 차단 우회 핵심)
        page = context.new_page()
        page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # 데이터 수집 호출
        kakao_res = get_kakao_data(context)
        naver_res = get_naver_data(context) # 위에서 만든 page를 쓰지 않고 context만 넘깁니다.
        
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        final_list = header + kakao_res + naver_res
        
        if len(final_list) > 1:
            sh.clear()
            sh.update('A1', final_list)
            print(f"🎊 완료! 총 {len(final_list)-1}건 저장.")
        else:
            print("⚠️ 여전히 수집된 데이터가 없습니다.")
        
        browser.close()
