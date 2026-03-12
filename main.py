# main.py
from naver import run_naver

import os
import json
import re
import requests
import datetime
from playwright.sync_api import sync_playwright

def run_kakao_realtime_rank():
    print("🚀 카카오페이지 [발행자·평점·댓글 포함] 수집 시작...")
    
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0.0.0 Safari/537.36"
            )
        )
        page = context.new_page()
        
        try:
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)
            
            links = page.eval_on_selector_all(
                'a[href*="/content/"]',
                'elements => elements.map(e => e.href)'
            )
            unique_links = []
            for link in links:
                if link not in unique_links:
                    unique_links.append(link)

            final_results = []
            today = datetime.datetime.now().strftime("%Y-%m-%d")
            
            for i, link in enumerate(unique_links[:20]):
                d_page = None
                try:
                    d_page = context.new_page()
                    d_page.goto(link, wait_until="networkidle")
                    d_page.wait_for_timeout(2500)

                    title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                    thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")
                    
                    author = "-"
                    author_el = d_page.locator('span.text-el-70.opacity-70').first
                    if author_el.count() > 0:
                        author = author_el.inner_text().strip()
                    
                    genre = "-"
                    genre_elements = d_page.locator('span.break-all.align-middle').all_inner_texts()
                    if len(genre_elements) > 1:
                        genre = [g for g in genre_elements if g != "웹소설"][0]
                    elif len(genre_elements) == 1:
                        genre = genre_elements[0].replace("웹소설", "").strip()

                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    # 발행자
                    publisher = "-"
                    publisher_block = d_page.locator(
                        'div.font-small1.flex.w-full.pt-6pxr'
                    ).filter(has_text="발행자").first
                    if publisher_block.count() > 0:
                        spans = publisher_block.locator("span")
                        if spans.count() >= 2:
                            publisher = spans.nth(1).inner_text().strip()

                    # 평점
                    rating = "-"
                    rating_el = d_page.locator('img[alt="별점"] + span.text-el-70.opacity-70')
                    if rating_el.count() > 0:
                        rating = rating_el.inner_text().strip()

                    # 댓글 수 (상단 요약: h3 제목이 "댓글"인 곳의 span)
                    comment_count = "-"
                    comment_header = d_page.locator('h3:has-text("댓글") span').first
                    if comment_header.count() > 0:
                        comment_count = comment_header.inner_text().strip()

                    final_results.append({
                        "rank": f"{i+1}위",
                        "title": title,
                        "author": author,
                        "date": today,
                        "genre": genre,
                        "views": views,
                        "thumbnail": thumbnail,
                        "publisher": publisher,
                        "rating": rating,
                        "comments": comment_count,
                    })
                    print(f"✅ {i+1}위 완료: {title}")
                except Exception as e:
                    print(f"❌ 카카오 상세({i+1}위) 에러: {e}")
                finally:
                    if d_page:
                        d_page.close()

            send_to_unified_sheet(final_results)

        except Exception as e:
            print(f"❌ 카카오 랭킹 에러: {e}")
        finally:
            browser.close()

def send_to_unified_sheet(data):
    WEBAPP_URL = os.environ.get("WEBAPP_URL")
    if not WEBAPP_URL:
        print("❌ WEBAPP_URL이 없습니다.")
        return

    payload = {
        "source": "kakao",
        "data": json.dumps(data),
    }

    try:
        response = requests.post(WEBAPP_URL, data=payload)
        print("📡 KAKAO 상태코드:", response.status_code)
        print("📡 KAKAO 응답:", response.text)
    except Exception as e:
        print(f"❌ 전송 중 예외 발생: {e}")

if __name__ == "__main__":
    run_kakao_realtime_rank()
    run_naver()
