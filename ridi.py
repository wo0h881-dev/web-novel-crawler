import os
import json
import datetime
import re
import requests
from bs4 import BeautifulSoup
from typing import Optional, Dict, List, Any

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


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_ridamu_text(text: str) -> str:
    text = clean_text(text)
    if not text:
        return text

    # 6시간 마다 -> 6시간마다
    text = re.sub(r"(\d+\s*시간)\s+마다", r"\1마다", text)
    text = re.sub(r"(\d+\s*일)\s+마다", r"\1마다", text)
    text = re.sub(r"(\d+\s*분)\s+마다", r"\1마다", text)

    # 1편 기다리면 무료 / 1화 기다리면 무료 형태 정리
    text = re.sub(r"\s+", " ", text).strip()
    return text


def unique_dict_list(items: List[Dict[str, Any]], key_fields: List[str]) -> List[Dict[str, Any]]:
    seen = set()
    result = []
    for item in items:
        key = tuple(item.get(k, "") for k in key_fields)
        if key in seen:
            continue
        seen.add(key)
        result.append(item)
    return result


def parse_ridi_promotion(item) -> Optional[Dict]:
    promo = {
        "timeFreeType": "none",
        "tag": "",
        "freeEpisodes": None,
        "daysLeft": None,
        "eventBanners": [],
        "notices": [],
        "benefits": [],
        "ridiWaitFree": False,
        "ridiFreeLabel": None,
        "ridiWaitFreeText": None,
        "serialSchedule": None,
        "exclusiveText": None,
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
            ridi_free_label = m.group(0)

    if not tag_parts and free_episodes is None and not ridi_waitfree:
        return None

    promo["tag"] = " ".join(tag_parts)
    promo["freeEpisodes"] = free_episodes
    promo["ridiWaitFree"] = ridi_waitfree
    promo["ridiFreeLabel"] = ridi_free_label

    return promo


def extract_row_header_text(row) -> str:
    header_el = row.select_one('[role="rowheader"]')
    if not header_el:
        return ""
    return clean_text(header_el.get_text(" ", strip=True))


def parse_notice_titles(row) -> List[Dict[str, Any]]:
    notices = []

    # 공지 제목 버튼만 수집
    # 원본 기준 제목 버튼은 화살표가 붙은 첫 번째 버튼이고,
    # 본문 버튼은 뒤쪽의 긴 설명문 버튼이라 제외한다.
    for btn in row.select("button"):
        text = clean_text(btn.get_text(" ", strip=True))
        if not text:
            continue

        if text in {"공지 더보기", "더 보기"}:
            continue

        # 본문성 긴 문장 제외
        if len(text) > 60:
            continue
        if text.endswith("부탁드립니다."):
            continue
        if "작품 이용에 참고 부탁드립니다" in text:
            continue
        if "독자님들의 많은 관심 부탁드립니다" in text:
            continue

        notices.append({
            "label": "공지",
            "title": text,
        })

    return unique_dict_list(notices, ["label", "title"])


def parse_benefits(row) -> List[Dict[str, Any]]:
    benefits = []

    for li in row.select("ul li"):
        title = None
        subtitle = None

        # 제목 후보
        title_candidates = [
            "span.rigrid-ke9tut",
            "a > div div span.rigrid-ke9tut",
            "a div span.rigrid-ke9tut",
        ]
        for sel in title_candidates:
            el = li.select_one(sel)
            if el:
                title = clean_text(el.get_text(" ", strip=True))
                if title:
                    break

        # 보조 설명 후보
        subtitle_candidates = [
            "div.rigrid-1tf5hrm",
            "div.rigrid-jpipff",
        ]
        for sel in subtitle_candidates:
            el = li.select_one(sel)
            if el:
                subtitle = clean_text(el.get_text(" ", strip=True))
                if subtitle:
                    break

        # 셀렉터가 깨질 때를 대비한 fallback
        if not title:
            texts = [
                clean_text(x.get_text(" ", strip=True))
                for x in li.select("span, div")
            ]
            texts = [t for t in texts if t]
            if texts:
                title = texts[0]
                if len(texts) >= 2:
                    subtitle = texts[-1] if texts[-1] != title else None

        if title:
            benefit = {
                "label": "혜택",
                "title": title,
            }
            if subtitle and subtitle != title:
                benefit["subtitle"] = subtitle
            benefits.append(benefit)

    return unique_dict_list(benefits, ["label", "title", "subtitle"])


def parse_event_banners(row) -> List[Dict[str, Any]]:
    events = []
    for a in row.select('a[href]'):
        text = clean_text(a.get_text(" ", strip=True))
        if not text:
            continue
        events.append({"title": text})
    return unique_dict_list(events, ["title"])


def parse_serial_schedule(row) -> Optional[str]:
    li_texts = [
        clean_text(li.get_text(" ", strip=True))
        for li in row.select("ul li")
    ]
    li_texts = [t for t in li_texts if t]
    return li_texts[0] if li_texts else None


def parse_exclusive_text(row) -> Optional[str]:
    text = clean_text(row.get_text(" ", strip=True))
    if not text:
        return None
    text = re.sub(r"^독점\s*", "", text).strip()
    return text or None


def parse_ridamu_text(row) -> Optional[str]:
    text = clean_text(row.get_text(" ", strip=True))
    if not text:
        return None
    text = re.sub(r"^리다무\s*", "", text).strip()
    text = re.sub(r"무료 이용 가능$", "", text).strip()
    text = normalize_ridamu_text(text)
    return text or None


def parse_ridi_detail_promotion(work_url: str) -> Optional[Dict]:
    if not work_url:
        return None

    try:
        soup = fetch_html(work_url)
    except Exception as e:
        print(f"⚠️ 리디 상세 수집 실패: {work_url} / {e}")
        return None

    detail = {
        "eventBanners": [],
        "notices": [],
        "benefits": [],
        "ridiWaitFreeText": None,
        "serialSchedule": None,
        "exclusiveText": None,
    }

    rows = soup.select('[role="row"]')
    if not rows:
        return None

    for row in rows:
        header = extract_row_header_text(row)
        if not header:
            continue

        if header == "연재":
            detail["serialSchedule"] = parse_serial_schedule(row)
            continue

        if header == "공지":
            detail["notices"] = parse_notice_titles(row)
            continue

        if header == "혜택":
            detail["benefits"] = parse_benefits(row)
            continue

        if header == "이벤트":
            detail["eventBanners"] = parse_event_banners(row)
            continue

        if header == "독점":
            detail["exclusiveText"] = parse_exclusive_text(row)
            continue

        if header == "리다무":
            detail["ridiWaitFreeText"] = parse_ridamu_text(row)
            continue

    has_any = any([
        detail["eventBanners"],
        detail["notices"],
        detail["benefits"],
        detail["ridiWaitFreeText"],
        detail["serialSchedule"],
        detail["exclusiveText"],
    ])

    return detail if has_any else None


def merge_ridi_promotion(base: Optional[Dict], detail: Optional[Dict]) -> Optional[Dict]:
    if not base and not detail:
        return None

    merged = {
        "timeFreeType": "none",
        "tag": "",
        "freeEpisodes": None,
        "daysLeft": None,
        "eventBanners": [],
        "notices": [],
        "benefits": [],
        "ridiWaitFree": False,
        "ridiFreeLabel": None,
        "ridiWaitFreeText": None,
        "serialSchedule": None,
        "exclusiveText": None,
    }

    if base:
        merged.update(base)

    if detail:
        if detail.get("eventBanners"):
            merged["eventBanners"] = detail["eventBanners"]

        if detail.get("notices"):
            merged["notices"] = detail["notices"]

        if detail.get("benefits"):
            merged["benefits"] = detail["benefits"]

        if detail.get("ridiWaitFreeText"):
            merged["ridiWaitFreeText"] = detail["ridiWaitFreeText"]

        if detail.get("serialSchedule"):
            merged["serialSchedule"] = detail["serialSchedule"]

        if detail.get("exclusiveText"):
            merged["exclusiveText"] = detail["exclusiveText"]

    has_any = any([
        merged.get("tag"),
        merged.get("freeEpisodes") is not None,
        merged.get("ridiWaitFree"),
        merged.get("ridiFreeLabel"),
        merged.get("eventBanners"),
        merged.get("notices"),
        merged.get("benefits"),
        merged.get("ridiWaitFreeText"),
        merged.get("serialSchedule"),
        merged.get("exclusiveText"),
    ])

    return merged if has_any else None


def parse_list(list_url: str, category_key: str):
    soup = fetch_html(list_url)

    cards = soup.select("li.fig-1m9tqaj")
    results = []

    for item in cards:
        title_tag = item.select_one("a.fig-w1hthz")
        if not title_tag:
            continue

        title = title_tag.get_text(strip=True)

        work_path = title_tag.get("href", "")
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

        author_tag = item.select_one("a.fig-103urjl.e1s6unbg0")
        publisher_tag = item.select_one("a.fig-103urjl.efs2tg41")

        author = author_tag.get_text(strip=True) if author_tag else "-"
        publisher = publisher_tag.get_text(strip=True) if publisher_tag else "-"

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

        total_ep_tag = item.select_one("span.fig-w746bu span")
        total_episodes = total_ep_tag.get_text(strip=True) if total_ep_tag else "-"

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

        if work_id:
            thumbnail_url = f"https://img.ridicdn.net/cover/{work_id}/large#1"
        else:
            thumbnail_url = "-"

        base_promotion = parse_ridi_promotion(item)
        detail_promotion = parse_ridi_detail_promotion(work_url) if work_url else None
        promotion = merge_ridi_promotion(base_promotion, detail_promotion)

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


def build_ridi_promotion_payload(raw_items):
    today = (datetime.datetime.utcnow() + datetime.timedelta(hours=9)).strftime("%Y-%m-%d")
    return {
        "date": today,
        "platform": "ridi",
        "items": [
            {
                "title": item["title"],
                "promotion": item["promotion"],
            }
            for item in raw_items
            if item.get("promotion")
        ],
    }


def save_ridi_promotions_json(raw_items):
    payload = build_ridi_promotion_payload(raw_items)
    os.makedirs("public/data", exist_ok=True)
    path = os.path.join("public", "data", "ridi-promotions-today.json")

    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print("💾 리디 프로모션 저장 완료:", path)


if __name__ == "__main__":
    items = run_ridi()

    for x in items[:30]:
        if "promotion" in x:
            print("PROMO:", x["카테고리"], x["title"], "=>", x["promotion"])

    save_ridi_promotions_json(items)
