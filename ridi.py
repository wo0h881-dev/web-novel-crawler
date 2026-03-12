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

        author = author_tag.get_text(strip=True) if author_tag else "-"
        publisher = publisher_tag.get_text(strip=True) if publisher_tag else "-"
        genre = genre_tag.get_text(strip=True) if genre_tag else "-"

        total_ep_tag = item.select_one("span.fig-w746bu span")
        total_episodes = total_ep_tag.get_text(strip=True) if total_ep_tag else "-"

        rating_block = item.select_one("span.fig-mhc4m4.enp6wb0")
        rating = "-"
        ridi_rating_count = "-"
        if rating_block:
            texts = [t for t in rating_block.stripped_strings]
            if texts:
                rating = texts[0]                 # "5.0"
            if len(texts) > 1:
                ridi_rating_count = texts[1].strip("()")  # "1,250"

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

        # 판타지만 썸네일 추가
        thumbnail_url = "-"
        if category_key == "fantasy":
            cover_div = item.select_one("div.fig-1wid0z5")
            if cover_div:
                style = cover_div.get("style", "")
                if "background-image" in style and "url(" in style:
                    start = style.find("url(") + 4
                    end = style.find(")", start)
                    if end > start:
                        thumb = style[start:end].strip('\'"')
                        if thumb.startswith("//"):
                            thumb = "https:" + thumb
                        thumbnail_url = thumb

        results.append({
            "카테고리": category_key,          # romance / rofan / fantasy / bl
            "rank": rank_value,               # "1위", "2위", "프로모션"...
            "is_promotion": is_promotion,     # True/False (원하면 시트에서 무시)
            "title": title,
            "author": author,
            "genre": genre,
            "출판사": publisher,
            "totalEpisodes": total_episodes,  # 네 카카오 형식에 맞춰서 이름 통일
            "rating": rating,
            "ridi_rating_count": ridi_rating_count,
            "thumbnail": thumbnail_url,       # 판타지만 값 있고 나머진 "-"
            "url": work_url,
        })

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
