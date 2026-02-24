import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [통합 랭킹 시스템] 전체 프로세스 시작...")
    
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        sh.clear()
        sh.update('A1', header)
        print("✅ 시트 초기화 완료")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}"); return

    with sync_playwright() as p:
        # 💡 네이버 수집을 위해 이번에는 headless=False로 시도해보는 것을 권장합니다.
        browser = p.chromium.launch(headless=True) 
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")

        # --- [STEP 1] 카카오페이지 수집 ---
        print("\n--- [1/2] 카카오페이지 수집 중 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="networkidle")
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]

            for i, link in enumerate(unique_links):
                try:
                    dp = context.new_page()
                    dp.goto(link, wait_until="networkidle")
                    title = dp.locator('meta[property="og:title"]').get_attribute("content")
                    thumb = dp.locator('meta[property="og:image"]').get_attribute("content")
                    author = dp.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    # [수정] 카카오 장르 추출 로직 복구
                    genre = "-"
                    genre_elements = dp.locator('span.break-all.align-middle').all_inner_texts()
                    if len(genre_elements) > 1:
                        genre = [g for g in genre_elements if g != "웹소설"][0]
                    elif len(genre_elements) == 1:
                        genre = genre_elements[0].replace("웹소설", "").strip()

                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위 완료: {title}")
                    dp.close()
                except: continue
        except Exception as e: print(f"❌ 카카오 에러: {e}")
        k_page.close()

        # --- [STEP 2] 네이버 시리즈 수집 ---
        print("\n--- [2/2] 네이버 시리즈 수집 중 ---")
        n_page = context.new_page()
        try:
            n_page.goto("https://series.naver.com/novel/top100List.series", wait_until="load")
            n_page.wait_for_timeout(5000) # 로딩 대기 충분히
            
            # [수정] 네이버 리스트 선택자를 더 포괄적으로 변경
            items = n_page.locator('div.lst_list_wrap li, ul.lst_list > li').all()
            print(f"   🔎 네이버 발견된 항목: {len(items)}개")

            for i, item in enumerate(items[:20]):
                try:
                    title_el = item.locator('h3 a').first
                    title = title_el.inner_text().strip()
                    href = title_el.get_attribute('href')
                    author = item.locator('span.author').first.inner_text().strip()
                    thumb = item.locator('img').first.get_attribute('src')
                    
                    # 네이버 리스트 페이지에서 장르 바로 가져오기
                    genre = item.locator('span.genre').inner_text().strip() if item.locator('span.genre').count() > 0 else "-"

                    detail_url = f"https://series.naver.com{href}"
                    dp = context.new_page()
                    dp.goto(detail_url, wait_until="domcontentloaded")
                    dp_text = dp.evaluate("() => document.body.innerText")
                    # 사용자님이 주신 <span>40.4만</span> 형태 추출
                    views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                    
                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위 완료: {title} ({views})")
                    dp.close()
                except: continue
        except Exception as e: print(f"❌ 네이버 에러: {e}")
        
        browser.close()
        print("\n🎊 수집 종료!")
