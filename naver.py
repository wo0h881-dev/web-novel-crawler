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

WEBAPP_URL = os.environ.get("WEBAPP_URL")  # GitHub Secrets 에서 주입


def get_product_no_from_href(href: str) -> str:
    qs = parse_qs(urlparse(href).query)
    return qs.get("productNo", [""])[0]


def fetch_views(detail_url: str) -> str:
    r = requests.get(detail_url, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    for span in soup.select("span"):
        text = span.get_text(strip=True)
        if any(u in text for u in ["만", "억"]) and any(ch.isdigit() for ch in text):
            return text
    return "-"


def fetch_naver_top20_raw():
    r = requests.get(RANKING_URL, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 네이버 TOP100 리스트 li 선택자
    lis = soup.select("#content > div > ul > li")

    items = []
    for rank, li in enumerate(lis[:20], start=1):
        # 제목, 상세 링크
        a = li.select_one("div.comic_cont h3 a") or li.select_one("h3 a")
        if not a:
            continue

        title = a.get_text(strip=True)
        href = a["href"]
        if href.startswith("/"):
            href = BASE + href
        product_no = get_product_no_from_href(href)

        # 작가
        author_tag = li.select_one("span.writer")
        author = author_tag.get_text(strip=True) if author_tag else "-"

        # 썸네일 규칙
        thumbnail_url = f"{BASE}/novel/img/{product_no}/{product_no}.jpg"

        # 누적 조회수
        views = fetch_views(href)

        items.append(
            {
                "rank": rank,
                "title": title,
                "author": author,
                "productNo": product_no,
                "detail_url": href,
                "thumbnail_url": thumbnail_url,
                "views": views,
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
                "genre": "웹소설",
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
        "source": "naver",          # Apps Script 에서 이 값으로 네이버 시트 선택
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
