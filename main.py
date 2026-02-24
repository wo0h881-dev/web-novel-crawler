import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [작가/장르/조회수] 최종 정제 수집 시작...")
    
    try:
        creds_json = os.environ['GOOGLE_CREDENTIALS']
        creds = json.loads(creds_json)
        gc = gspread.service_account_from_dict(creds)
        sheet_id = "1c2ax0-3t70NxvxL-cXeOCz9NYnSC9OhrzC0IOWSe5Lc" 
        sh = gc.open_by_key(sheet_id).sheet1
        print("✅ 구글 시트 연결 성공")
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

            # 1. 메인 랭킹에서 작품 상세 링크 추출
            links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = []
            for link in links:
                if link not in unique_links: unique_links.append(link)
            
            # 헤더 구성: [순위, 타이틀, 작가, 장르, 조회수, 수집일]
            data_to_push = [["순위", "타이틀", "작가", "장르", "조회수", "수집일"]]
            
            # 2. 상위 20개 작품 상세 페이지 침투
            for i, link in enumerate(unique_links[:20]):
                try:
                    detail_page = context.new_page()
                    detail_page.goto(link, wait_until="networkidle")
                    detail_page.wait_for_timeout(2000)

                    # [데이터 추출]
                    # 타이틀
                    title = detail_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # 작가 (제목 바로 아래 위치한 텍스트 요소 타겟팅)
                    # 상세페이지 내에서 'text-el-70' 클래스 중 첫 번째가 보통 작가명입니다.
                    author = detail_page.locator('div[class*="text-el-70"]').first.inner_text().strip()
                    
                    # 장르 (아이콘 옆 텍스트) - '웹소설' 단어 삭제 정제
                    genre_raw = detail_page.locator('span[class*="text-el-70"]').first.inner_text().strip()
                    genre = genre_raw.replace("웹소설", "").replace("·", "").strip()
                    
                    # 조회수
                    all_text = detail_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만|억])', all_text)
                    views = view_match.group(1) if view_match else "-"

                    data_to_push.append([f"{i+1}위", title, author, genre, views, "2026-02-24"])
                    print(f"✅ {i+1}위 수집 성공: {title} ({author} / {genre})")
                    
                    detail_page.close()
                except Exception as e:
                    print(f"⚠️ {i+1}위 수집 중 스킵: {e}")
                    continue

            # 3. 구글 시트 최종 업데이트
            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 모든 작업이 완료되었습니다! 시트를 확인해보세요.")

        except Exception as e:
            print(f"❌ 에러 발생: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
