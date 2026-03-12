# naver.py : 네이버 시리즈 웹소설 TOP 20 크롤링 후 구글 웹앱으로 전송
import os
import json
import datetime
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

BASE = "https://series.naver.com"
RANKING_URL = (
    "https://series.naver.com/novel/top100List.series"
    "?rankingTypeCode=DAILY&categoryCode=ALL"
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    ),
}

WEBAPP_URL = os.environ.get("WEBAPP_URL")


def get_product_no_from_href(href: str) -> str:
    qs = parse_qs(urlparse(href).query)
    return qs.get("productNo", [""])[0]


def fetch_detail_info(detail_url: str):
    """
    상세 페이지에서 조회수, 작가명, 장르, 썸네일, 출판사, 평점, 댓글 수를 가져온다.
    반환: (views, author, genre, thumbnail_url, publisher, rating, comment_count)
    """
    r = requests.get(detail_url, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 1) 조회수
    views = "-"
    for span in soup.select("span"):
        text = span.get_text(strip=True)
        if any(u in text for u in ["만", "억"]) and any(ch.isdigit() for ch in text):
            views = text
            break

    # 2) 작가
    author = "-"
    author_label = soup.find(
        lambda tag: tag.name == "span" and tag.get_text(strip=True) == "글"
    )
    if author_label:
        a = author_label.find_next("a")
        if a:
            author = a.get_text(strip=True)
    if author == "-":
        writer_tag = soup.select_one(".writer")
        if writer_tag:
            author = writer_tag.get_text(strip=True)

    # 3) 장르
    genre = "웹소설"
    info_lst = soup.find("li", class_="info_lst")
    if info_lst:
        genre_links = info_lst.select('a[href*="genreCode="]')
        if genre_links:
            first_genre = genre_links[0].get_text(strip=True)
            if first_genre:
                genre = first_genre

    # 4) 썸네일
    thumbnail_url = "-"
    img_tag = soup.select_one(
        "div.pic img, div.thumb img, img#product_img, img[src*='comicthumb-phinf']"
    )
    if img_tag and img_tag.has_attr("src"):
        thumbnail_url = img_tag["src"].strip()

    # 5) 출판사
    publisher = "-"
    pub_label = soup.find(
        lambda tag: tag.name == "span" and tag.get_text(strip=True) == "출판사"
    )
    if pub_label:
        pub_a = pub_label.find_next("a")
        if pub_a:
            publisher = pub_a.get_text(strip=True)

    # 6) 평점
    rating = "-"
    score_area = soup.select_one("div.score_area")
    if score_area:
        em = score_area.find("em")
        if em:
            rating = em.get_text(strip=True)

    # 7) 댓글 전체 수 (숫자만 추출)
    comment_count = "-"
    comment_header = soup.find(
        lambda tag: tag.name == "h3"
        and "댓글" in tag.get_text()
        and tag.find("span")
    )
    if comment_header:
        total_span = comment_header.find("span")
        if total_span:
            text = total_span.get_text(strip=True)   # 예: "10,281" 또는 "전체 10,281"
            m = re.search(r"(\d[\d,]*)", text)
            if m:
                comment_count = m.group(1).replace(",", "")

    return views, author, genre, thumbnail_url, publisher, rating, comment_count


def fetch_naver_top20_raw():
    r = requests.get(RANKING_URL, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    lis = soup.select("#content > div > ul > li")

    items = []
    for rank, li in enumerate(lis[:20], start=1):
        a = li.select_one("div.comic_cont h3 a") or li.select_one("h3 a")
        if not a:
            continue

        title = a.get_text(strip=True)
        href = a["href"]
        if href.startswith("/"):
            href = BASE + href
        product_no = get_product_no_from_href(href)

        (
            views,
            author,
            genre,
            thumbnail_url,
            publisher,
            rating,
            comment_count,
        ) = fetch_detail_info(href)

        items.append(
            {
                "rank": rank,
                "title": title,
                "author": author,
                "genre": genre,
                "productNo": product_no,
                "detail_url": href,
                "thumbnail_url": thumbnail_url,
                "views": views,
                "출판사": publisher,
                "rating": rating,
                "comments": comment_count,
            }
        )

    return items


def build_payload_for_google(raw_items):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    result = []

    for item in raw_items:
        result.append(
            {
                "rank": f"{item['rank']}위",
                "title": item["title"],
                "author": item.get("author") or "-",
                "date": today,
                "genre": item.get("genre", "웹소설"),
                "views": item.get("views", "-"),
                "thumbnail": item.get("thumbnail_url", "-"),
                "출판사": item.get("출판사", "-"),
                "rating": item.get("rating", "-"),
                "comments": item.get("comments", "-"),
            }
        )
    return result


def send_to_google_webapp(data):
    if not WEBAPP_URL:
        print("❌ WEBAPP_URL 환경변수가 없습니다.")
        return

    payload = {
        "source": "naver",
        "data": json.dumps(data),
    }

    resp = requests.post(WEBAPP_URL, data=payload)
    print("📡 NAVER 상태코드:", resp.status_code)
    print("📡 NAVER 응답:", resp.text)


def run_naver():
    print("🚀 네이버 시리즈 TOP20 수집 시작...")
    raw_items = fetch_naver_top20_raw()
    data_for_sheet = build_payload_for_google(raw_items)
    send_to_google_webapp(data_for_sheet)
    print("✅ 네이버 전송 완료")


if __name__ == "__main__":
    run_naver()
