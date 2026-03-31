# naver.py : 네이버 시리즈 웹소설 TOP 20 크롤링 + 프로모션 정보 수집

import os
import json
import datetime
import re
import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs
from typing import Optional, Dict

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


# ---------------- 프로모션 파싱 ----------------

def parse_promotion_from_list_li(li) -> Optional[Dict]:
    """
    TOP100 리스트 <li> 하나에서 프로모션 정보 추출.
    - timeFreeType: waitFree / threeHour / pass / none
    - tag: 썸네일 아이콘 텍스트(매일10시무료, 타임딜, 시리즈 에디션 등)
    - freeEpisodes: '25화 무료'에서 숫자
    - daysLeft: '85일 남음'에서 숫자
    """
    thumb_a = li.select_one("a.pic")
    tag_parts = []
    time_free_type = "none"

    # 썸네일 위 아이콘들 (매일10시무료, 타임딜, 시리즈 에디션 등)
    if thumb_a:
        ico_els = thumb_a.select("em")
        for em in ico_els:
            text = em.get_text(strip=True)
            if not text:
                blind = em.select_one(".blind")
                if blind:
                    text = blind.get_text(strip=True)
            if not text:
                continue

            tag_parts.append(text)

            if "매일10시무료" in text:
                time_free_type = "waitFree"
            elif "타임딜" in text:
                time_free_type = "threeHour"

    # '총130화/미완결|25화 무료  85일 남음' 줄
    meta_el = li.select_one(".comic_cont .info") or li.select_one(".info")
    meta_text = meta_el.get_text(" ", strip=True) if meta_el else ""

    free_episodes = None
    m1 = re.search(r"(\d+)\s*화\s*무료", meta_text)
    if m1:
        free_episodes = int(m1.group(1))

    days_left = None
    m2 = re.search(r"(\d+)\s*일\s*남음", meta_text)
    if m2:
        days_left = int(m2.group(1))

    full_text = " ".join(tag_parts) + " " + meta_text

    # 프리패스/에디션 계열
    if time_free_type == "none":
        if "에디션" in full_text or "프리패스" in full_text:
            time_free_type = "pass"

    tag = " ".join(tag_parts).strip()

    if (
        time_free_type == "none"
        and free_episodes is None
        and days_left is None
        and not tag
    ):
        return None

    return {
        "timeFreeType": time_free_type,
        "tag": tag or "프로모션",
        "freeEpisodes": free_episodes,
        "daysLeft": days_left,
        "eventBanners": [],
        "notices": [],
    }


# ---------------- 상세 페이지 파싱 ----------------

def fetch_detail_info(detail_url: str):
    """
    상세 페이지에서 조회수, 작가명, 장르, 썸네일, 출판사, 평점, 댓글 수, 총 회차수를 가져온다.
    반환: (views, author, genre, thumbnail_url, publisher, rating, comment_count, total_episodes)
    """
    r = requests.get(detail_url, headers=HEADERS)
    r.raise_for_status()
    soup = BeautifulSoup(r.text, "html.parser")

    # 1) 조회수 (942.4만 같은 값)
    views = "-"
    try:
        dl_btn = soup.select_one("a.btn_download span")
        if dl_btn:
            text = dl_btn.get_text(strip=True)
            if any(u in text for u in ["만", "억"]) and any(ch.isdigit() for ch in text):
                views = text
    except Exception:
        pass

    if views == "-":
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

    # 7) 댓글 수
    comment_count = "-"
    try:
        c_span = soup.select_one("span#commentCount")
        if c_span:
            comment_count = c_span.get_text(strip=True)
    except Exception:
        pass

    # 8) 총 회차수
    total_episodes = "-"
    try:
        ep_header = soup.select_one("h5.end_total_episode")
        if ep_header:
            strong = ep_header.find("strong")
            if strong:
                num = strong.get_text(strip=True)
                total_episodes = f"{num}화"
    except Exception:
        pass

    return (
        views,
        author,
        genre,
        thumbnail_url,
        publisher,
        rating,
        comment_count,
        total_episodes,
    )


# ---------------- 랭킹 페이지 ----------------

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

        promotion = parse_promotion_from_list_li(li)

        (
            views,
            author,
            genre,
            thumbnail_url,
            publisher,
            rating,
            comment_count,
            total_episodes,
        ) = fetch_detail_info(href)

        item = {
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
            "totalEpisodes": total_episodes,
        }
        if promotion:
            item["promotion"] = promotion

        items.append(item)

    return items


# ---------------- 시트로 보내는 포맷 ----------------

def build_payload_for_google(raw_items):
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    result = []

    for item in raw_items:
        base = {
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
            "totalEpisodes": item.get("totalEpisodes", "-"),
        }
        if item.get("promotion"):
            base["promotion"] = item["promotion"]
        result.append(base)

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

    # 로컬 확인용
    for row in data_for_sheet:
        if "promotion" in row:
            print("PROMO:", row["rank"], row["title"], row["promotion"])

    os.makedirs("out", exist_ok=True)
    path = os.path.join("out", "naver-top20.json")
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data_for_sheet, f, ensure_ascii=False, indent=2)
    print("💾 저장 완료:", path)

    # 실제 시트 연동 시에만 사용
    # send_to_google_webapp(data_for_sheet)
    print("✅ 네이버 수집 완료")


if __name__ == "__main__":
    run_naver()
