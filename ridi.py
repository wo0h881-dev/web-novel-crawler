# ridi.py
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

def parse_list(list_url: str, category_key: str):
    soup = fetch_html(list_url)

    # 제목 링크 기준으로 카드 찾기
    cards = []
    for a in soup.select("a.fig-w1hthz"):
        card = a.find_parent("li")
        if not card:
            card = a.find_parent("div")
        if card and card not in cards:
            cards.append(card)

    results = []

    for item in cards:
        title_tag = item.select_one("a.fig-w1hthz")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)
        work_url = title_tag.get("href", "")
        if work_url and work_url.startswith("/"):
            work_url = BASE_URL + work_url

        author_tag = item.select_one("a.fig-103urjl.e1s6unbg0")
        publisher_tag = item.select_one("a.fig-103urjl.efs2tg41")
        genre_tag = item.select_one("span.fig-gcx8hj.e1g90d6s0")

        author = author_tag.get_text(strip=True) if author_tag else None
        publisher = publisher_tag.get_text(strip=True) if publisher_tag else None
        genre = genre_tag.get_text(strip=True) if genre_tag else None

        total_ep_tag = item.select_one("span.fig-w746bu span")
        total_episodes = total_ep_tag.get_text(strip=True) if total_ep_tag else None

        rating_block = item.select_one("span.fig-mhc4m4.enp6wb0")
        rating = None
        ridi_rating_count = None
        if rating_block:
            texts = [t for t in rating_block.stripped_strings]
            if texts:
                rating = texts[0]          # "5.0"
            if len(texts) > 1:
                ridi_rating_count = texts[1].strip("()")  # "1,250"

        badge = item.select_one("div.fig-ty289v")
        is_promotion = False
        rank_value = None
        if badge:
            badge_text = badge.get_text(strip=True)
            if badge_text.isdigit():
                rank_value = int(badge_text)
            else:
                if badge.select_one("svg"):
                    is_promotion = True

        # 판타지만 썸네일 추가
        thumbnail_url = None
        if category_key == "fantasy":
            cover_div = item.select_one("div.fig-1wid0z5")
            if cover_div:
                style = cover_div.get("style", "")
                # style 예: background-image:url("https://...jpg")
                if "background-image" in style and "url(" in style:
                    start = style.find("url(") + 4
                    end = style.find(")", start)
                    if end > start:
                        thumb = style[start:end].strip('\'"')
                        if thumb.startswith("//"):
                            thumb = "https:" + thumb
                        thumbnail_url = thumb

        results.append({
            "source": "ridi",
            "category_key": category_key,      # romance / rofan / fantasy / bl
            "title": title,
            "author": author,
            "publisher": publisher,
            "genre": genre,
            "total_episodes": total_episodes,
            "rating": rating,
            "ridi_rating_count": ridi_rating_count,
            "rank": rank_value,
            "is_promotion": is_promotion,
            "thumbnail_url": thumbnail_url,    # 판타지만 값 있음, 나머지는 None
            "url": work_url,
        })

    return results

def fetch_ridi_all():
    all_items = []
    for key, url in CATEGORY_URLS.items():
        try:
            items = parse_list(url, key)
        except Exception as e:
            # 필요하면 로깅
            continue
        all_items.extend(items)
    return all_items
