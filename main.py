import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_total_ranking():
    print("🚀 [통합 랭킹 시스템] 전체 프로세스 시작...")
    
    # 1. 구글 시트 연결 및 초기화
    try:
        creds = json.loads(os.environ['GOOGLE_CREDENTIALS'])
        gc = gspread.service_account_from_dict(creds)
        # ⚠️ 본인의 시트 ID를 입력하세요
        sh = gc.open_by_key("1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc").sheet1
        
        # 헤더 작성 및 기존 내용 초기화
        header = [["순위", "플랫폼", "타이틀", "작가", "장르", "조회수", "썸네일", "수집일"]]
        sh.clear()
        sh.update('A1', header)
        print("✅ 시트 초기화 및 헤더 작성 완료")
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    with sync_playwright() as p:
        # 💡 네이버 차단이 의심되면 headless=False로 변경하세요.
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
        )

        # --- [STEP 1] 카카오페이지 수집 ---
        print("\n--- [1/2] 카카오페이지 수집 및 기록 시작 ---")
        k_page = context.new_page()
        try:
            k_page.goto("https://page.kakao.com/menu/10011/screen/94", wait_until="networkidle")
            k_page.wait_for_timeout(3000)
            links = k_page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = list(dict.fromkeys(links))[:20]

            for i, link in enumerate(unique_links):
                try:
                    dp = context.new_page()
                    dp.goto(link, wait_until="networkidle")
                    title = dp.locator('meta[property="og:title"]').get_attribute("content")
                    thumb = dp.locator('meta[property="og:image"]').get_attribute("content")
                    author = dp.locator('span.text-el-70.opacity-70').first.inner_text().strip()
                    
                    # 조회수 추출
                    body = dp.evaluate("() => document.body.innerText")
                    views = re.search(r'(\d+\.?\d*[만|억])', body).group(1) if re.search(r'(\d+\.?\d*[만|억])', body) else "-"
                    
                    # 시트에 즉시 기록
                    sh.append_row([f"{i+1}위", "카카오페이지", title, author, "장르", views, thumb, "2026-02-25"])
                    print(f"   ✅ 카카오 {i+1}위 기록 완료: {title}")
                    dp.close()
                except: continue
        except Exception as e:
            print(f"❌ 카카오 수집 중 오류: {e}")
        k_page.close()

        # --- [STEP 2] 네이버 시리즈 수집 ---
        print("\n--- [2/2] 네이버 시리즈 수집 및 기록 시작 ---")
        n_page = context.new_page()
        try:
            n_page.goto("https://series.naver.com/novel/top100List.series", wait_until="networkidle")
            n_page.wait_for_timeout(5000)
            
            # 🔍 봇 차단 여부 체크
            page_content = n_page.content()
            bot_keywords = ["서비스 이용이 제한되었습니다", "비정상적인 접근", "Captcha", "로봇이 아닙니다"]
            
            if any(kw in page_content for kw in bot_keywords):
                print("🚨 [경고] 네이버가 봇으로 감지하여 차단을 걸었습니다!")
                sh.append_row(["-", "네이버 시리즈", "봇 차단됨", "에러", "-", "-", "-", "2026-02-25"])
            else:
                items = n_page.locator('ul.lst_list > li, .lst_list_wrap li').all()
                print(f"   🔎 네이버 발견된 항목: {len(items)}개")

                if len(items) == 0:
                    print("⚠️ 발견된 항목이 0개입니다. (차단은 아니나 구조 확인 필요)")
                
                for i, item in enumerate(items[:20]):
                    try:
                        # 주신 HTML 기반 선택자
                        title_el = item.locator('h3 a').first
                        title = title_el.inner_text().strip()
                        href = title_el.get_attribute('href')
                        author = item.locator('span.author').first.inner_text().strip()
                        thumb = item.locator('img').first.get_attribute('src')

                        # 상세페이지 조회수
                        detail_url = f"https://series.naver.com{href}"
                        dp = context.new_page()
                        dp.goto(detail_url, wait_until="domcontentloaded")
                        dp_text = dp.evaluate("() => document.body.innerText")
                        views = re.search(r'(\d+\.?\d*[만|억])', dp_text).group(1) if re.search(r'(\d+\.?\d*[만|억])', dp_text) else "-"
                        
                        # 시트에 즉시 기록
                        sh.append_row([f"{i+1}위", "네이버 시리즈", title, author, "장르", views, thumb, "2026-02-25"])
                        print(f"   ✅ 네이버 {i+1}위 기록 완료: {title} ({views})")
                        dp.close()
                    except: continue
        except Exception as e:
            print(f"❌ 네이버 수집 중 오류: {e}")
        n_page.close()

        browser.close()
        print("\n🎊 모든 수집 프로세스가 종료되었습니다!")

if __name__ == "__main__":
    run_total_ranking()
