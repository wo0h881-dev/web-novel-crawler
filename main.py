from naver import run_naver, save_naver_promotions_json, fetch_naver_top20_raw
from ridi import run_ridi, save_ridi_promotions_json

import os
import json
import re
import requests
import datetime
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup


def extract_time_free_type(d_page):
    """
    3다무 / 기다무 / 없음 구분
    """
    try:
        badge_img = d_page.query_selector(
            'img[alt*="다무"], img[alt*="기다"], img[alt*="무료"]'
        )
        if not badge_img:
            return "none"
        alt = badge_img.get_attribute("alt") or ""
        if "3다무" in alt or "3시간" in alt:
            return "threeHour"
        if "기다무" in alt or "기다리면 무료" in alt:
            return "waitFree"
        return "none"
    except Exception:
        return "none"


def extract_kakao_promotion_from_notice_tab(d_page):
    """
    카카오 '소식' 탭에서:
      - 상단 이벤트 배너들 (eventBanners 배열)
      - 공지 카드들의 [라벨/제목/날짜]만 추출
    """
    promotion = {
        "eventBanners": [],  # 🔹 여러 배너
        "notices": [],
    }

    try:
        # 1) 소식 탭으로 이동
        try:
            notice_tab = d_page.locator(
                "span.font-small1",
                has_text="소식",
            ).first
            if notice_tab.count() > 0:
                notice_tab.click()
                d_page.wait_for_timeout(1000)
        except Exception as e:
            print("NOTICE_TAB_ERR:", e)

        html = d_page.content()
        soup = BeautifulSoup(html, "html.parser")

        # 2) 상단 이벤트 배너들 (관련이벤트 컨테이너 안의 모든 배너)
        banner_container = soup.select_one('div[data-t-obj*="관련이벤트"]')
        if banner_container:
            event_banners = []
            for banner_div in banner_container.select("div.relative.flex.h-64pxr"):
                t = banner_div.select_one(".font-medium2-bold")
                s = banner_div.select_one(".font-small2")
                if not t:
                    continue
                event_banners.append(
                    {
                        "title": t.get_text(strip=True),
                        "subtitle": s.get_text(strip=True) if s else "",
                    }
                )
            if event_banners:
                promotion["eventBanners"] = event_banners

        # 3) 공지 카드들: 안내 / 제목 / 날짜
        notice_blocks = soup.select(
            "div.flex.w-full.flex-col.items-center.rounded-12pxr.bg-bg-a-20"
        )

        for block in notice_blocks:
            header = block.select_one("div.flex.flex-col.space-y-8pxr.pt-18pxr")
            if not header:
                continue

            label_el = header.select_one("span.font-x-small2-bold")
            title_el = header.select_one("div.font-small1-bold")
            date_el = header.select_one("span.font-small2")

            label = label_el.get_text(strip=True) if label_el else ""
            title = title_el.get_text(strip=True) if title_el else ""
            date = date_el.get_text(strip=True) if date_el else ""

            if not title or not date:
                continue

            promotion["notices"].append(
                {
                    "label": label or "안내",
                    "title": title,
                    "date": date,
                }
            )

    except Exception as e:
        print("PROMOTION_PARSE_ERR:", e)

    if not promotion["eventBanners"] and not promotion["notices"]:
        return None
    return promotion



def save_kakao_promotions(results, date_str):
    items = []
    for item in results:
        promo = item.get("promotion") or {}
        if not promo:
            continue
        items.append(
            {
                "title": item.get("title", ""),
                "promotion": promo,
            }
        )

    payload = {
        "date": date_str,
        "platform": "kakao",
        "items": items,
    }

    os.makedirs("public/data", exist_ok=True)
    path = os.path.join("public", "data", "kakao-promotions-today.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    print("💾 카카오 프로모션 저장:", path)


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
                "elements => elements.map(e => e.href)",
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
                    title = d_page.locator(
                        'meta[property="og:title"]'
                    ).get_attribute("content")
                    thumbnail = d_page.locator(
                        'meta[property="og:image"]'
                    ).get_attribute("content")

                    # 2) 작가
                    author = "-"
                    author_el = d_page.locator(
                        "span.text-el-70.opacity-70"
                    ).first
                    if author_el.count() > 0:
                        author = author_el.inner_text().strip()

                    # 3) 장르
                    genre = "-"
                    genre_elements = d_page.locator(
                        "span.break-all.align-middle"
                    ).all_inner_texts()
                    if len(genre_elements) > 1:
                        genre = [g for g in genre_elements if g != "웹소설"][0]
                    elif len(genre_elements) == 1:
                        genre = genre_elements[0].replace("웹소설", "").strip()

                    # 4) 조회수 (본문 텍스트에서 첫 번째 '만/억' 패턴)
                    body_text = d_page.evaluate("() => document.body.innerText")
                    view_match = re.search(r"(\d+\.?\d*[만억])", body_text)
                    views = view_match.group(1) if view_match else "-"

                    # 5) 정보 탭으로 이동 (발행자용)
                    try:
                        info_tab = d_page.locator(
                            "span.font-small1",
                            has_text="정보",
                        ).first
                        info_count = info_tab.count()
                        print("INFO_TAB_COUNT:", info_count)
                        if info_count > 0:
                            info_tab.click()
                            d_page.wait_for_timeout(800)
                    except Exception as e:
                        print("INFO_TAB_ERR:", e)

                    # 6) 출판사
                    publisher = "-"
                    try:
                        publisher_row = d_page.locator(
                            "div.font-small1"
                        ).filter(has_text="발행자").first
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

                    # 8) 다시 홈 탭으로 이동
                    try:
                        home_tab = d_page.locator(
                            "span.font-small1",
                            has_text="홈",
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
                            "div.flex.h-full.flex-1.items-center.space-x-8pxr"
                        ).first
                        if episode_container.count() > 0:
                            ep_text_el = episode_container.locator(
                                "span.text-ellipsis.break-all.line-clamp-1.font-small2-bold.text-el-70"
                            ).first
                            if ep_text_el.count() > 0:
                                ep_text = ep_text_el.inner_text().strip()
                                m = re.search(r"(\d[\d,]*)", ep_text)
                                if m:
                                    num = m.group(1).replace(",", "")
                                    total_episodes = f"{num}화"

                        # 댓글 컨테이너 (두 번째)
                        comment_container = d_page.locator(
                            "div.flex.h-full.flex-1.items-center.space-x-8pxr"
                        ).nth(1)
                        if comment_container.count() > 0:
                            c_text_el = comment_container.locator(
                                "span.text-ellipsis.break-all.line-clamp-1.font-small2-bold.text-el-70"
                            ).first
                            if c_text_el.count() > 0:
                                c_text = c_text_el.inner_text().strip()
                                m2 = re.search(r"([\d.,]+)", c_text)
                                if m2:
                                    core = m2.group(1)
                                    if "만" in c_text:
                                        comments = core + "만"
                                    else:
                                        comments = core.replace(",", "")
                    except Exception as e:
                        print("EP/COMMENT_ERR:", e)

                    # 10) 프로모션 정보
                    time_free_type = extract_time_free_type(d_page)
                    promotion = extract_kakao_promotion_from_notice_tab(d_page)

                    final_item = {
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
                    }

                    if time_free_type != "none" or promotion:
                        final_item["promotion"] = {
                            "timeFreeType": time_free_type,
                            **(promotion or {"notices": []}),
                        }

                    final_results.append(final_item)
                    print(f"✅ {i+1}위 완료: {title}")

                except Exception as e:
                    print(f"❌ 카카오 상세({i+1}위) 에러: {e}")
                finally:
                    if d_page:
                        d_page.close()

            # 시트로 전송
            send_to_unified_sheet(final_results, source="kakao")

            # Cloudflare용 프로모션 JSON 저장
            save_kakao_promotions(final_results, today)

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
    results = run_ridi()
    if not results:
        print("⚠ 리디 결과 없음")
        return
    send_to_unified_sheet(results, source="ridi")
    save_ridi_promotions_json(results)
    print("✅ 리디 전송 완료")


if __name__ == "__main__":
    run_kakao_realtime_rank()
    run_naver()
    run_ridi_all()
