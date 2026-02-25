# naver.py : 네이버 시리즈 웹소설 TOP 20 크롤링 후 구글 웹앱으로 전송

import os
import json
import datetime
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

BASE = "https://series.naver.com"
RANKING_URL = (
    "https://series.naver.com/novel/top100List.series"
    "?rankingTypeCode=DAILY&categoryCode=ALL"
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                  "AppleWebKit/537.36 (KHTML, like Gecko) "
                  "Chrome/122.0 Safari/537.36",
}

# GitHub Actions 에서 넣어주는 구글 웹앱 URL
WEBAPP_URL = os.environ.get("WEBAPP_URL")


def get_product_no_from_href(href: str) -> str:
    qs = parse_qs(urlparse(href).query)
    return qs.get("productNo", [""])[0]


def fetch_detail_info(detail_url: str):
    """
    상세 페이지에서 누적 조회수, 작가명, 장르, 썸네일을 한 번에 가져온다.
    반환: (views, author, genre, thumbnail_url)
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

    # 3) 장르 (info_lst 안에서)
    genre = "웹소설"
    info_lst = soup.find("li", class_="info_lst")
    if info_lst:
        genre_links = info_lst.select('a[href*="genreCode="]')
        if genre_links:
            first_genre = genre_links[0].get_text(strip=True)
            if first_genre:
                genre = first_genre

    # 4) 썸네일: 상세 상단 대표 이미지 src (지금 보여준 구조 기준)
    thumbnail_url = "-"
    # 상세 상단에 있는 커버 이미지 하나만 잡기
    img_tag = soup.select_one("div.pic img, div.thumb img, img#product_img, img[src*='comicthumb-phinf']")
    if img_tag and img_tag.has_attr("src"):
        thumbnail_url = img_tag["src"].strip()

    return views, author, genre, thumbnail_url



def fetch_naver_top20_raw():
    """
    네이버 시리즈 웹소설 일간 TOP 20을 랭킹 페이지 + 상세 페이지에서 수집.
    """
    r = requests.get(RANKING_URL, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # TOP100 리스트 li 선택자
    lis = soup.select("#content > div > ul > li")

    items = []
    for rank, li in enumerate(lis[:20], start=1):
        # 제목 / 상세 URL
        a = li.select_one("div.comic_cont h3 a") or li.select_one("h3 a")
        if not a:
            continue

        title = a.get_text(strip=True)
        href = a["href"]
        if href.startswith("/"):
            href = BASE + href
        product_no = get_product_no_from_href(href)

        # 썸네일 (규칙 기반)
        thumbnail_url = f"{BASE}/novel/img/{product_no}/{product_no}.jpg"

        # 상세 페이지에서 조회수 / 작가 / 장르
        views, author, genre = fetch_detail_info(href)

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
            }
        )

    return items


def build_payload_for_google(raw_items):
    """
    구글 웹앱이 기대하는 형식으로 변환.
    (source: 'naver', data: JSON 배열)
    """
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
            }
        )
    return result


def send_to_google_webapp(data):
    if not WEBAPP_URL:
        print("❌ WEBAPP_URL 환경변수가 없습니다.")
        return

    payload = {
        "source": "naver",          # Apps Script 에서 네이버 시트로 보낼 기준
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
