import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실시간 랭킹] 100% 정밀 수집 시작...")
    
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
            # 1. 랭킹 페이지 접속 및 링크 수집
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(4000)
            page.mouse.wheel(0, 2000) # 넉넉히 스크롤
            page.wait_for_timeout(2000)

            links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = []
            for link in links:
                if link not in unique_links: unique_links.append(link)
            
            data_to_push = [["순위", "타이틀", "작가", "장르", "조회수", "수집일"]]
            
            # 2. 상위 20개 상세 페이지 정밀 수집
            for i, link in enumerate(unique_links[:20]):
                try:
                    detail_page = context.new_page()
                    detail_page.goto(link, wait_until="networkidle")
                    detail_page.wait_for_timeout(2000)

                    # [타이틀]
                    title = detail_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # [작가] - 알려주신 span 태그와 클래스 조합으로 정밀 타겟팅
                    # 클래스가 여러개일 경우 핵심인 text-el-70과 작가명이 들어가는 위치를 고려합니다.
                    author_el = detail_page.locator('span.text-el-70.opacity-70').first
                    author = author_el.inner_text().strip() if author_el.count() > 0 else "-"
                    
                    # [장르] - '웹소설' 단어 삭제 및 정제
                    genre_el = detail_page.locator('span.break-all.align-middle').first
                    genre_raw = genre_el.inner_text().strip() if genre_el.count() > 0 else "-"
                    genre = genre_raw.replace("웹소설", "").replace("·", "").replace(" ", "").strip()
                    
                    # [조회수] - 숫자 + 억/만 패턴 정밀 추출
                    view_el = detail_page.locator('span.text-el-70.opacity-70').last # 보통 작가 아래쪽에 위치
                    view_raw = view_el.inner_text().strip() if view_el.count() > 0 else "-"
                    # 만약 위에서 잡은게 조회수가 아니라면 전체 텍스트에서 재검색
                    if "억" not in view_raw and "만" not in view_raw:
                        all_text = detail_page.evaluate("() => document.body.innerText")
                        match = re.search(r'(\d+\.?\d*[만|억])', all_text)
                        view_raw = match.group(1) if match else "-"

                    data_to_push.append([f"{i+1}위", title, author, genre, view_raw, "2026-02-24"])
                    print(f"✅ {i+1}위 수집 완료: {title} | {author} | {genre} | {view_raw}")
                    
                    detail_page.close()
                except Exception as e:
                    print(f"⚠️ {i+1}위 수집 중 오류: {e}")
                    continue

            # 3. 구글 시트 업데이트
            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 [작가/장르/조회수] 모든 데이터가 완벽하게 정제되어 저장되었습니다!")

        except Exception as e:
            print(f"❌ 전체 실행 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
