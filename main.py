import os
import json
import gspread
import re
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [실제 순위 & 장르 정제] 최종 수집 시작...")
    
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
            
            # [순위 보정] 화면을 충분히 내려서 모든 숫자가 로딩되게 함
            page.mouse.wheel(0, 2000)
            page.wait_for_timeout(3000)

            # 1. 실제 화면에 보이는 '작품 카드'들만 정확히 타겟팅
            # 카카오 페이지의 리스트 아이템들을 순서대로 가져옵니다.
            items = page.query_selector_all('div.flex-1.cursor-pointer')
            
            ranking_data = []
            for item in items:
                link_el = item.query_selector('a[href*="/content/"]')
                # 순번 숫자 추출 (이미지 옆에 써있는 1, 2, 3...)
                rank_el = item.query_selector('p.font-bold2') # 카카오 순위 숫자 클래스
                if link_el and rank_el:
                    rank_num = rank_el.inner_text().strip()
                    ranking_data.append({"rank": f"{rank_num}위", "url": link_el.href_as_str() if hasattr(link_el, 'href_as_str') else page.evaluate("el => el.href", link_el)})

            data_to_push = [["순위", "타이틀", "작가", "장르", "조회수", "수집일"]]
            
            # 2. 수집된 실제 순서(20개)대로 상세 페이지 진입
            for i, info in enumerate(ranking_data[:20]):
                try:
                    detail_page = context.new_page()
                    detail_page.goto(info["url"], wait_until="networkidle")
                    detail_page.wait_for_timeout(1500)

                    title = detail_page.locator('meta[property="og:title"]').get_attribute("content")
                    
                    # 작가 추출 (알려주신 클래스 기준)
                    author_el = detail_page.locator('span.text-el-70.opacity-70').first
                    author = author_el.inner_text().strip() if author_el.count() > 0 else "-"
                    
                    # [장르 정제 로직] 모든 텍스트 중 '웹소설'이 포함된 줄을 찾아 장르만 추출
                    all_spans = detail_page.locator('span').all_inner_texts()
                    genre = "-"
                    for s in all_spans:
                        if "웹소설" in s:
                            # '웹소설', '·', 공백 제거
                            genre = s.replace("웹소설", "").replace("·", "").replace(" ", "").strip()
                            break
                    
                    # 조회수 추출
                    view_match = re.search(r'(\d+\.?\d*[만|억])', detail_page.evaluate("() => document.body.innerText"))
                    views = view_match.group(1) if view_match else "-"

                    data_to_push.append([info["rank"], title, author, genre, views, "2026-02-24"])
                    print(f"✅ {info['rank']} 완료: {title} | {genre}")
                    detail_page.close()
                except:
                    continue

            # 3. 시트 업데이트
            sh.clear()
            sh.update('A1', data_to_push)
            print("🎊 [실제 순위 일치 + 장르 정제] 완료!")

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

if __name__ == "__main__":
    run_kakao_realtime_rank()
