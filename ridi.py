# ridi.py
import requests
import re
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

    # 작품 카드 리스트 확보
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

        # 작가 / 출판사
        author_tag = item.select_one("a.fig-103urjl.e1s6unbg0")
        publisher_tag = item.select_one("a.fig-103urjl.efs2tg41")

        author = author_tag.get_text(strip=True) if author_tag else "-"
        publisher = publisher_tag.get_text(strip=True) if publisher_tag else "-"

        # ── 장르: 세부장르 + 카테고리 조합 ──
        genre_tag = item.select_one("span.fig-gcx8hj.e1g90d6s0")
        sub_genre = genre_tag.get_text(strip=True) if genre_tag else "-"

        if category_key == "romance":
            # 로맨스: "로맨스 · 현대물"
            main_genre = "로맨스"
            genre = f"{main_genre} · {sub_genre}" if sub_genre != "-" else main_genre

        elif category_key == "rofan":
            # 로판: "서양풍 로판" / "동양풍 로판" 그대로
            genre = sub_genre if sub_genre != "-" else "로맨스판타지"

        elif category_key == "fantasy":
            # 판타지: "현대 판타지" / "퓨전 판타지" 그대로
            genre = sub_genre if sub_genre != "-" else "판타지"

        elif category_key == "bl":
            # BL: "BL · 현대물" / "BL · 판타지물"
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

        # 평점 숫자 (별 옆 5.0)
        rating_block = item.select_one("span.fig-mhc4m4.enp6wb0")
        if rating_block:
            texts = [t for t in rating_block.stripped_strings]
            if texts:
                rating = texts[0]

        # 평가수 "(9,330)"
        rating_count_span = item.select_one("span.fig-1d0qko5.enp6wb2")
        if rating_count_span:
            raw_count = "".join(rating_count_span.stripped_strings)  # "(9,330)"
            raw_count = raw_count.strip("()")
            ridi_rating_count = raw_count if raw_count else "-"

        # ── 순위 / 프로모션 ──
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

        # ── 썸네일: 카드 HTML에서 /cover/ URL을 정규식으로 직접 추출 ──
        thumbnail_url = "-"
        html = item.decode_contents()  # 카드 내부 HTML 문자열

        m = re.search(r"https://img\.ridicdn\.net/cover/[^\s\"']+", html)
        if m:
            thumbnail_url = m.group(0)

        results.append({
            "카테고리": category_key,          # romance / rofan / fantasy / bl
            "rank": rank_value,               # "1위", "2위", "프로모션" ...
            "is_promotion": is_promotion,     # True/False
            "title": title,
            "author": author,
            "genre": genre,
            "출판사": publisher,
            "totalEpisodes": total_episodes,
            "rating": rating,
            "ridi_rating_count": ridi_rating_count,
            "thumbnail": thumbnail_url,
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
