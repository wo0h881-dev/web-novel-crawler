import os
import json
import gspread
import re
import time
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [에러 수정 버전] 수집 시스템 가동...")
    
    try:
        creds_raw = os.environ.get('GOOGLE_CREDENTIALS')
        creds = json.loads(creds_raw)
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 시트 ID를 입력하세요
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        # ✅ 시트 업데이트 방식 수정 (에러 방지)
        header = ["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]
        sh.clear()
        sh.insert_row(header, 1)
        print("✅ 시트 초기화 성공")
    except Exception as e:
        print(f"❌ 시트 접속/초기화 에러: {e}"); return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            viewport={'width': 1280, 'height': 800}
        )

        # --- [STEP 1] 카카오페이지 ---
        print("\n--- [1/2] 카카오페이지 수집 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="domcontentloaded", timeout=60000)
            k_page.wait_for_timeout(3000)
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]

            for i, link in enumerate(unique_links):
                try:
                    dp = context.new_page()
                    dp.goto(link, wait_until="domcontentloaded", timeout=20000)
                    title = dp.locator('meta[property="og:title"]').get_attribute("content") or "제목없음"
                    thumb = dp.locator('meta[property="og:image"]').get_attribute("content") or ""
                    author_el = dp.locator('span.text-el-70.opacity-70').first
                    author = author_el.inner_text().strip() if author_el.count() > 0 else "-"
                    
                    genre = "-"
                    g_elements = dp.locator('span.break-all.align-middle').all_inner_texts()
                    if len(g_elements) > 1: genre = [g for g in g_elements if g != "웹소설"][0]
                    elif len(g_elements) == 1: genre = g_elements[0].replace("웹소설", "").strip()

                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위: {title}")
                    dp.close()
                except: continue
        except Exception as e: print(f"❌ 카카오 메인 에러: {e}")

        # --- [STEP 2] 네이버 시리즈 ---
        print("\n--- [2/2] 네이버 시리즈 수집 ---")
        n_page = context.new_page()
        try:
            # 해외 IP 차단 대비를 위해 PC 랭킹 주소 사용
            n_page.goto("https://series.naver.com/novel/top100List.series", wait_until="domcontentloaded", timeout=60000)
            n_page.wait_for_timeout(5000)
            
            items = n_page.locator('ul.lst_list > li, div.lst_list_wrap li').all()
            if not items:
                print("   ⚠️ PC 버전 응답 없음, 모바일 재시도...")
                n_page.goto("https://m.series.naver.com/novel/top100List.series", wait_until="domcontentloaded", timeout=60000)
                n_page.wait_for_timeout(5000)
                items = n_page.locator('a.comic_top_ba, ul.lst_list > li').all()

            print(f"   🔎 네이버 발견 항목: {len(items)}개")

            for i, item in enumerate(items[:20]):
                try:
                    title_el = item.locator('h3 a, dt a, h5.tit, .tit, strong').first
                    title = title_el.inner_text().replace("새로운 에피소드", "").strip()
                    
                    # 작가 및 썸네일
                    author = item.locator('.author, .wt, span.author').first.inner_text().strip()
                    thumb = item.locator('img').first.get_attribute('src') or ""
                    
                    # 상세페이지 이동 (조회수)
                    href = title_el.get_attribute('href') or item.locator('a').first.get_attribute('href')
                    full_href = href if href.startswith('http') else f"https://series.naver.com{href}"
                    
                    dp = context.new_page()
                    dp.goto(full_href, wait_until="domcontentloaded", timeout=20000)
                    dp_text = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                    
                    sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, "웹소설", views, thumb, "2026-02-25"])
                    print(f"   ✅ 네이버 {i+1}위: {title}")
                    dp.close()
                except: continue
        except Exception as e: print(f"❌ 네이버 메인 에러: {e}")

        browser.close()
        print("\n🎊 모든 수집 프로세스 종료")

if __name__ == "__main__":
    run_total_ranking()
