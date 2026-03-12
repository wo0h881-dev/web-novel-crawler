# main.py
from naver import run_naver
from ridi import run_ridi  # ← 이 줄을 따로

import os
import json
import re
import requests
import datetime
from playwright.sync_api import sync_playwright



def run_kakao_realtime_rank():
    print("🚀 카카오페이지 수집 시작...")

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
            # 실시간 랭킹 페이지
            url = "https://page.kakao.com/menu/10011/screen/94"
            page.goto(url, wait_until="networkidle")
            page.wait_for_timeout(5000)

            # 작품 링크 수집
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

            # 상위 20개 상세 정보 수집
            for i, link in enumerate(unique_links[:20]):
                d_page = None
                try:
                    d_page = context.new_page()
                    d_page.goto(link, wait_until="networkidle")
                    d_page.wait_for_timeout(2500)

                    # 0) 기본 대기
                    d_page.wait_for_timeout(1000)

                    # 1) 타이틀 / 썸네일
                    title = d_page.locator('meta[property="og:title"]').get_attribute("content")
                    thumbnail = d_page.locator('meta[property="og:image"]').get_attribute("content")

                    # 2) 작가
                    author = "-"
                    author_el = d_page.locator('span.text-el-70.opacity-70').first
                    if author_el.count() > 0:
                        author = author_el.inner_text().strip()

                    # 3) 장르
                    genre = "-"
                    genre_elements = d_page.locator('span.break-all.align-middle').all_inner_texts()
                    if len(genre_elements) > 1:
                        genre = [g for g in genre_elements if g != "웹소설"][0]
                    elif len(genre_elements) == 1:
                        genre = genre_elements[0].replace("웹소설", "").strip()

                    # 4) 조회수 (본문 텍스트에서 첫 번째 '만/억' 패턴)
                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r'(\d+\.?\d*[만억])', body_text)
                    views = view_match.group(1) if view_match else "-"

                    # 5) 정보 탭으로 이동 (발행자용)
                    try:
                        info_tab = d_page.locator(
                            'span.font-small1',
                            has_text="정보"
                        ).first
                        info_count = info_tab.count()
                        print("INFO_TAB_COUNT:", info_count)
                        if info_count > 0:
                            info_tab.click()
                            d_page.wait_for_timeout(800)
                    except Exception as e:
                        print("INFO_TAB_ERR:", e)

                    # 6) 출판사: "발행자" 라벨 줄의 두 번째 span
                    publisher = "-"
                    try:
                        publisher_row = d_page.locator('div.font-small1').filter(
                            has_text="발행자"
                        ).first
                        row_count = publisher_row.count()
                        print("PUB_ROW_COUNT:", row_count)
                        if row_count > 0:
                            spans = publisher_row.locator("span")
                            span_count = spans.count()
                            print("PUB_SPAN_COUNT:", span_count)
                            if span_count >= 2:
                                publisher = spans.nth(1).inner_text().strip()
                    except Exception as e:
                        print("PUB_ERR:", e)

                    print("PUB:", publisher)

                    # 7) 평점
                    rating = "-"
                    rating_el = d_page.locator(
                        'img[alt="별점"] + span.text-el-70.opacity-70'
                    )
                    if rating_el.count() > 0:
                        rating = rating_el.inner_text().strip()

                    # 8) 다시 홈 탭으로 이동 (회차수/댓글수 홈 기준)
                    try:
                        home_tab = d_page.locator(
                            'span.font-small1',
                            has_text="홈"
                        ).first
                        if home_tab.count() > 0:
                            home_tab.click()
                            d_page.wait_for_timeout(800)
                    except Exception as e:
                        print("HOME_TAB_ERR:", e)

                    # 9) 총 회차수 & 댓글 수
                    total_episodes = "-"
                    comments = "-"

                    try:
                        # 회차수 컨테이너 (첫 번째)
                        episode_container = d_page.locator(
                            'div.flex.h-full.flex-1.items-center.space-x-8pxr'
                        ).first
                        if episode_container.count() > 0:
                            ep_text_el = episode_container.locator(
                                'span.text-ellipsis.break-all.line-clamp-1.font-small2-bold.text-el-70'
                            ).first
                            if ep_text_el.count() > 0:
                                ep_text = ep_text_el.inner_text().strip()  # "전체 146"
                                m = re.search(r"(\d[\d,]*)", ep_text)
                                if m:
                                    num = m.group(1).replace(",", "")
                                    total_episodes = f"{num}화"

                        # 댓글 컨테이너 (두 번째)
                        comment_container = d_page.locator(
                            'div.flex.h-full.flex-1.items-center.space-x-8pxr'
                        ).nth(1)
                        if comment_container.count() > 0:
                            c_text_el = comment_container.locator(
                                'span.text-ellipsis.break-all.line-clamp-1.font-small2-bold.text-el-70'
                            ).first
                            if c_text_el.count() > 0:
                                c_text = c_text_el.inner_text().strip()   # "전체 7,171" 또는 "전체 1.6만"
                                # 숫자 + 선택적 소수점까지
                                m2 = re.search(r"([\d.,]+)", c_text)
                                if m2:
                                    core = m2.group(1)  # "7,171" 또는 "1.6"
                                    if "만" in c_text:
                                        comments = core + "만"     # "1.6만"
                                    else:
                                        comments = core.replace(",", "")  # "7171"
                    except Exception as e:
                        print("EP/COMMENT_ERR:", e)

                    final_results.append({
                        "rank": f"{i+1}위",
                        "title": title,
                        "author": author,
                        "date": today,
                        "genre": genre,
                        "views": views,
                        "thumbnail": thumbnail,
                        "출판사": publisher,
                        "rating": rating,
                        "totalEpisodes": total_episodes,
                        "comments": comments,
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


def send_to_unified_sheet(data, source="kakao"):
    WEBAPP_URL = os.environ.get("WEBAPP_URL")
    if not WEBAPP_URL:
        print("❌ WEBAPP_URL이 없습니다.")
        return

    payload = {
        "source": source,
        "data": json.dumps(data),
    }

    try:
        response = requests.post(WEBAPP_URL, data=payload)
        print(f"📡 {source.upper()} 상태코드:", response.status_code)
        print(f"📡 {source.upper()} 응답:", response.text)
    except Exception as e:
        print(f"❌ {source} 전송 중 예외 발생: {e}")


def run_ridi_all():
    print("🚀 리디 수집 시작...")
    results = run_ridi()  # ridi.py에서 가져온 리스트
    if not results:
        print("⚠ 리디 결과 없음")
        return
    send_to_unified_sheet(results, source="ridi")
    print("✅ 리디 전송 완료")


if __name__ == "__main__":
    run_kakao_realtime_rank()
    run_naver()
    run_ridi_all()
