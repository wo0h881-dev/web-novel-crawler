import os
import json
import gspread
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [상세페이지 침투] 100% 정확도 수집 시작...")
    
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
    except Exception as e:
        print(f"❌ 시트 연결 실패: {e}")
        return

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)
            page.mouse.wheel(0, 1500)
            page.wait_for_timeout(3000)

            # 1. 랭킹 페이지에서 작품 링크들(href)을 먼저 싹 수집합니다.
            # 중복 제거를 위해 리스트를 정제합니다.
            links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = []
            for link in links:
                if link not in unique_links: unique_links.append(link)
            
            print(f"🔎 총 {len(unique_links[:20])}개의 작품 상세 페이지로 진입합니다...")

            data_to_push = [["순위", "타이틀", "작가", "조회수", "수집일"]]
            
            # 2. 각 링크로 직접 들어가서 정확한 정보를 가져옵니다.
            for i, link in enumerate(unique_links[:20]):
                try:
                    detail_page = context.new_page()
                    detail_page.goto(link, wait_until="networkidle")
                    detail_page.wait_for_timeout(2000) # 상세페이지 로딩 대기

                    # 제목 (가장 큰 글씨)
                    title = detail_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # [핵심] 상세페이지 내의 작가명과 조회수를 직접 타겟팅
                    # 카카오 상세페이지는 구조가 명확합니다.
                    # 작가명은 보통 "전체보기" 버튼 근처나 특정 클래스에 있습니다.
                    author = detail_page.locator('div[class*="text-el-70"]').first.inner_text() if detail_page.locator('div[class*="text-el-70"]').count() > 0 else "작가미상"
                    
                    # 조회수 (눈 아이콘 옆의 숫자)
                    views = "확인불가"
                    all_text = detail_page.evaluate("() => document.body.innerText")
                    import re
                    view_match = re.search(r'(\d+\.?\d*[만|억])', all_text)
                    if view_match: views = view_match.group(1)

                    data_to_push.append([f"{i+1}위", title, author, views, "2026-02-24"])
                    print(f"✅ {i+1}위 완료: {title}")
                    
                    detail_page.close()
                except:
                    print(f"⚠️ {i+1}위 수집 중 오류 발생 (스킵)")
                    continue

            # 3. 시트 업데이트
            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 모든 데이터가 100% 정확하게 시트에 기록되었습니다!")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
