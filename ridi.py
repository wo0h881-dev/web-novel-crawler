# ridi.py : 리디북스 카테고리별 웹소설 베스트셀러 + 프로모션(리다무 / N화 무료)

import re
import requests
from bs4 import BeautifulSoup

BASE_URL = "https://ridibooks.com"

CATEGORY_URLS = {
    "romance": "https://ridibooks.com/bestsellers/romance_serial",
    "rofan": "https://ridibooks.com/bestsellers/romance_fantasy_serial",
    "fantasy": "https://ridibooks.com/bestsellers/fantasy_serial",
    "bl": "https://ridibooks.com/bestsellers/bl-webnovel",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0.0.0 Safari/537.36"
    )
}


def fetch_html(url: str) -> BeautifulSoup:
    resp = requests.get(url, headers=HEADERS, timeout=10)
    resp.raise_for_status()
    return BeautifulSoup(resp.text, "html.parser")


def parse_ridi_promotion(item) -> dict | None:
    """
    작품 카드(li.fig-1m9tqaj) 하나에서 리디 프로모션 뱃지를 파싱.
    - timeFreeType: 리다무면 waitFree
    - freeEpisodes: N화 무료 숫자
    - ridiWaitFree: 리다무 여부 (리디 전용)
    - ridiFreeLabel: '3화 무료' 같은 텍스트 (리디 전용)
    """
    promo = {
        "timeFreeType": "none",   # 공통 필드
        "tag": "",
        "freeEpisodes": None,
        "daysLeft": None,
        "eventBanners": [],
        "notices": [],
        "ridiWaitFree": False,
        "ridiFreeLabel": None,
    }

    thumb_link = item.select_one("a.fig-1q776eq, a.fig-1q776eq.e1ftn9sh1, a.fig-w1hthz")
    if not thumb_link:
        return None

    badges = thumb_link.select("ul.fig-1i4k0g9 li[aria-label]")

    tag_parts = []
    free_episodes = None
    ridi_free_label = None
    ridi_waitfree = False

    for li in badges:
        label = li.get("aria-label", "").strip()
        if not label:
            continue

        tag_parts.append(label)

        if "리다무" in label:
            promo["timeFreeType"] = "waitFree"
            ridi_waitfree = True

        m = re.search(r"(\d+)\s*화\s*무료", label)
        if m:
            free_episodes = int(m.group(1))
            ridi_free_label = m.group(0)  # "3화 무료"

    if not tag_parts and free_episodes is None and not ridi_waitfree:
        return None

    promo["tag"] = " ".join(tag_parts)
    promo["freeEpisodes"] = free_episodes
    promo["ridiWaitFree"] = ridi_waitfree
    promo["ridiFreeLabel"] = ridi_free_label

    return promo


def parse_list(list_url: str, category_key: str):
    soup = fetch_html(list_url)

    # 각 작품 카드는 li.fig-1m9tqaj
    cards = soup.select("li.fig-1m9tqaj")
    results = []

    for item in cards:
        # 제목 링크
        title_tag = item.select_one("a.fig-w1hthz")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)

        # 작품 URL + 작품 ID 추출
        work_path = title_tag.get("href", "")  # "/books/6188000001?_rdt..."
        work_url = ""
        work_id = ""

        if work_path:
            if work_path.startswith("/"):
                work_url = BASE_URL + work_path
            else:
                work_url = work_path

            m_id = re.search(r"/books/(\d+)", work_path)
            if m_id:
                work_id = m_id.group(1)

        # 작가 / 출판사
        author_tag = item.select_one("a.fig-103urjl.e1s6unbg0")
        publisher_tag = item.select_one("a.fig-103urjl.efs2tg41")

        author = author_tag.get_text(strip=True) if author_tag else "-"
        publisher = publisher_tag.get_text(strip=True) if publisher_tag else "-"

        # ── 장르 ──
        genre_tag = item.select_one("span.fig-gcx8hj.e1g90d6s0")
        sub_genre = genre_tag.get_text(strip=True) if genre_tag else "-"

        if category_key == "romance":
            main_genre = "로맨스"
            genre = f"{main_genre} · {sub_genre}" if sub_genre != "-" else main_genre
        elif category_key == "rofan":
            genre = sub_genre if sub_genre != "-" else "로맨스판타지"
        elif category_key == "fantasy":
            genre = sub_genre if sub_genre != "-" else "판타지"
        elif category_key == "bl":
            main_genre = "BL"
            genre = f"{main_genre} · {sub_genre}" if sub_genre != "-" else main_genre
        else:
            genre = sub_genre or "웹소설"

        # 총 회차
        total_ep_tag = item.select_one("span.fig-w746bu span")
        total_episodes = total_ep_tag.get_text(strip=True) if total_ep_tag else "-"

        # ── 평점 / 평가수 ──
        rating = "-"
        ridi_rating_count = "-"

        rating_block = item.select_one("span.fig-mhc4m4.enp6wb0")
        if rating_block:
            texts = [t for t in rating_block.stripped_strings]
            if texts:
                rating = texts[0]

        rating_count_span = item.select_one("span.fig-1d0qko5.enp6wb2")
        if rating_count_span:
            raw_count = "".join(rating_count_span.stripped_strings)
            raw_count = raw_count.strip("()")
            ridi_rating_count = raw_count if raw_count else "-"

        # ── 순위 / 프로모션 뱃지 ──
        badge = item.select_one("div.fig-ty289v")
        is_promotion = False
        rank_value = "-"
        if badge:
            badge_text = badge.get_text(strip=True)
            if badge_text.isdigit():
                rank_value = f"{int(badge_text)}위"
            else:
                if badge.select_one("svg"):
                    is_promotion = True
                    rank_value = "프로모션"

        # ── 썸네일: 작품 ID로 직접 생성 ──
        if work_id:
            thumbnail_url = f"https://img.ridicdn.net/cover/{work_id}/large#1"
        else:
            thumbnail_url = "-"

        # ── 리디 프로모션(리다무 / n화 무료) ──
        promotion = parse_ridi_promotion(item)

        result = {
            "카테고리": category_key,
            "rank": rank_value,
            "is_promotion": is_promotion,
            "title": title,
            "author": author,
            "genre": genre,
            "출판사": publisher,
            "totalEpisodes": total_episodes,
            "rating": rating,
            "ridi_rating_count": ridi_rating_count,
            "thumbnail": thumbnail_url,
            "url": work_url,
        }
        if promotion:
            result["promotion"] = promotion

        results.append(result)

    return results


def run_ridi():
    all_results = []
    for key, url in CATEGORY_URLS.items():
        try:
            items = parse_list(url, key)
            all_results.extend(items)
        except Exception as e:
            print(f"❌ 리디 {key} 에러: {e}")
    return all_results


if __name__ == "__main__":
    items = run_ridi()
    for x in items[:30]:
        if "promotion" in x:
            print("PROMO:", x["카테고리"], x["title"], "=>", x["promotion"])
