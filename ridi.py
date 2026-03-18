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

        author_tag = item.select_one("a.fig-103urjl.e1s6unbg0")
        publisher_tag = item.select_one("a.fig-103urjl.efs2tg41")
        genre_tag = item.select_one("span.fig-gcx8hj.e1g90d6s0")

        author = author_tag.get_text(strip=True) if author_tag else "-"
        publisher = publisher_tag.get_text(strip=True) if publisher_tag else "-"
        genre = genre_tag.get_text(strip=True) if genre_tag else "-"

        # ✅ BL 베스트 페이지에서 온 작품은 상단 카테고리를 BL로 고정
        # (리스트 장르가 현대물/역사/판타지물 등으로 찍혀도 최종 장르는 BL)
        if category_key == "bl":
            genre = "BL"

        total_ep_tag = item.select_one("span.fig-w746bu span")
        total_episodes = total_ep_tag.get_text(strip=True) if total_ep_tag else "-"

                # 평점 / 평가수
        rating = "-"
        ridi_rating_count = "-"

        # 평점 숫자
        rating_block = item.select_one("span.fig-mhc4m4.enp6wb0")
        if rating_block:
            texts = [t for t in rating_block.stripped_strings]
            if texts:
                rating = texts[0]

        # 평가수 "(9,323)" 부분
        rating_count_span = item.select_one("span.fig-1d0qko5.enp6wb2")
        if rating_count_span:
            raw_count = "".join(rating_count_span.stripped_strings)  # "(9,323)"
            raw_count = raw_count.strip("()")
            ridi_rating_count = raw_count if raw_count else "-"


        # ✅ 프로모션(★) vs 숫자 랭크 구분
        badge = item.select_one("div.fig-ty289v")
        is_promotion = False
        rank_value = "-"
        if badge:
            badge_text = badge.get_text(strip=True)
            if badge_text.isdigit():
                # "1" -> "1위"
                rank_value = f"{int(badge_text)}위"
            else:
                # SVG 아이콘이 있으면 프로모션 슬롯(★)
                if badge.select_one("svg"):
                    is_promotion = True
                    rank_value = "프로모션"

        # ✅ 판타지 카테고리만 리스트 썸네일 파싱 (19금 여부는 상세쪽에서 추가 설계 가능)
               # ✅ 썸네일: 리스트 카드 안의 img 태그에서 직접 src 사용
        thumbnail_url = "-"
        # 클래스는 페이지마다 조금 바뀔 수 있어서, 우선 카드 내부 img 하나를 잡는 방식
        img_tag = item.select_one("img.fig-7uq04e.e99ij5y0")
        if not img_tag:
            # 혹시 클래스가 바뀐 경우를 대비한 fallback
            img_tag = item.select_one("img")
        if img_tag:
            src = img_tag.get("src", "").strip()
            if src:
                # 프로토콜이 없으면 보정
                if src.startswith("//"):
                    src = "https:" + src
                thumbnail_url = src


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
