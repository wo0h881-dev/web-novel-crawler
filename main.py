import os
import json
import gspread
import re
import time
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [통합 수집 시스템] 고도화 버전 가동...")
    
    try:
        creds_raw = os.environ.get('GOOGLE_CREDENTIALS')
        creds = json.loads(creds_raw)
        gc = gspread.service_account_from_dict(creds)
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        sh.clear()
        sh.update('A1', header)
    except Exception as e:
        print(f"❌ 시트 설정 오류: {e}"); return

    with sync_playwright() as p:
        # 브라우저 실행 (차단 확률을 낮추기 위해 더 정교한 설정 사용)
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
            locale="ko-KR"
        )

        # --- [STEP 1] 카카오페이지 ---
        print("\n--- [1/2] 카카오페이지 수집 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="load", timeout=60000)
            k_page.wait_for_timeout(3000)
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]

            for i, link in enumerate(unique_links):
                try:
                    dp = context.new_page()
                    dp.goto(link, wait_until="load")
                    title = dp.locator('meta[property="og:title"]').get_attribute("content")
                    thumb = dp.locator('meta[property="og:image"]').get_attribute("content")
                    author = dp.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    genre = "-"
                    g_elements = dp.locator('span.break-all.align-middle').all_inner_texts()
                    if len(g_elements) > 1: genre = [g for g in g_elements if g != "웹소설"][0]
                    elif len(g_elements) == 1: genre = g_elements[0].replace("웹소설", "").strip()

                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, genre, views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위 완료: {title}")
                    dp.close()
                except: continue
        except Exception as e: print(f"❌ 카카오 에러: {e}")

        # --- [STEP 2] 네이버 시리즈 (강력한 우회 버전) ---
        print("\n--- [2/2] 네이버 시리즈 수집 시작 ---")
        n_page = context.new_page()
        try:
            # 주소를 PC 버전 랭킹으로 변경 (해외 IP 차단이 모바일보다 덜한 경우가 많음)
            n_url = "https://series.naver.com/novel/top100List.series"
            n_page.goto(n_url, wait_until="domcontentloaded", timeout=60000)
            
            # 🔍 [봇 감지 체크]
            content = n_page.content()
            if "제한되었습니다" in content or "Captcha" in content:
                print("🚨 [봇 감지] 네이버가 시스템 접근을 차단했습니다. (해외 IP 차단)")
                sh.append_row(["-", "네이버", "차단됨", "에러", "-", "-", "-", "2026-02-25"])
            else:
                # 리스트가 로드될 때까지 기다림 (더 유연한 선택자 사용)
                n_page.wait_for_timeout(5000)
                # PC 버전의 리스트 항목: .lst_list 안의 li들
                items = n_page.locator('.lst_list > li, .lst_list_wrap li, ul.lst_list > li').all()
                
                print(f"   🔎 네이버 발견 항목: {len(items)}개")

                for i, item in enumerate(items[:20]):
                    try:
                        # PC 버전과 모바일 버전을 모두 고려한 범용 추출
                        title_el = item.locator('h3 a, dt a, .tit').first
                        title = title_el.inner_text().replace("새로운 에피소드", "").strip()
                        
                        href = title_el.get_attribute('href')
                        author = item.locator('.author, .wt').first.inner_text().strip()
                        thumb = item.locator('img').first.get_attribute('src')

                        # 상세페이지 조회수
                        dp = context.new_page()
                        dp.goto(f"https://series.naver.com{href}", wait_until="domcontentloaded")
                        dp_text = dp.evaluate("() => document.body.innerText")
                        views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                        
                        sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, "웹소설", views, thumb, "2026-02-25"])
                        print(f"   ✅ 네이버 {i+1}위 완료: {title}")
                        dp.close()
                    except: continue
        except Exception as e:
            print(f"❌ 네이버 최종 실패: {e}")

        browser.close()
        print("\n🎊 모든 수집 프로세스 종료!")

if __name__ == "__main__":
    run_total_ranking()
