import os
import json
import re
import requests
import datetime
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [플랫폼 & 썸네일] 통합 전송 버전 수집 시작...")
    
    with sync_playwright() as p:
        # 브라우저 실행
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36")
        page = context.new_page()
        
        try:
            # 카카오 실시간 랭킹 페이지
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)
            
            # 메인 화면 링크 수집
            links = page.eval_on_selector_all('a[href*="/content/"]', 'elements => elements.map(e => e.href)')
            unique_links = []
            for link in links:
                if link not in unique_links: unique_links.append(link)

            final_results = []
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            # 상위 20개 상세 수집
            for i, link in enumerate(unique_links[:20]):
                try:
                    d_page = context.new_page()
                    d_page.goto(link, wait_until="networkidle")
                    d_page.wait_for_timeout(2500)

                    # 1. 타이틀 및 썸네일
                    title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                    thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")
                    
                    # 2. 작가
                    author = "-"
                    author_el = d_page.locator('span.text-el-70.opacity-70').first
                    if author_el.count() > 0:
                        author = author_el.inner_text().strip()
                    
                    # 3. 장르
                    genre = "-"
                    genre_elements = d_page.locator('span.break-all.align-middle').all_inner_texts()
                    if len(genre_elements) > 1:
                        genre = [g for g in genre_elements if g != "웹소설"][0]
                    elif len(genre_elements) == 1:
                        genre = genre_elements[0].replace("웹소설", "").strip()

                    # 4. 조회수
                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만|억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    # 통합 규격에 맞춰 데이터 저장
                    final_results.append({
                        "rank": f"{i+1}위",
                        "title": title,
                        "author": author,
                        "date": today,
                        "genre": genre,
                        "views": views,
                        "thumbnail": thumbnail
                    })
                    print(f"✅ {i+1}위 완료: {title}")
                    d_page.close()
                except:
                    continue

            # 🚀 중앙 관제 구글 웹앱으로 데이터 전송
            send_to_unified_sheet(final_results)

        except Exception as e:
            print(f"❌ 에러: {e}")
        finally:
            browser.close()

def send_to_unified_sheet(data):
    # GitHub Secrets에 저장된 구글 웹앱 URL (끝이 /exec인 것)
    WEBAPP_URL = os.environ.get("WEBAPP_URL")
    
    if not WEBAPP_URL:
        print("❌ 에러: WEBAPP_URL 환경변수가 없습니다.")
        return

    payload = {
        "source": "kakao",
        "data": json.dumps(data)
    }

    try:
        response = requests.get(WEBAPP_URL, params=payload)
        print(f"📡 전송 결과: {response.text}")
    except Exception as e:
        print(f"❌ 전송 오류: {e}")

if __name__ == "__main__":
    run_kakao_realtime_rank()
