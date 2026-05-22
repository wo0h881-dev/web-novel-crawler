import atexit
import datetime
import json
import os
import re
from typing import Any, Dict, List, Optional

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

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
    ),
    "Accept": (
        "text/html,application/xhtml+xml,application/xml;q=0.9,"
        "image/avif,image/webp,image/apng,*/*;q=0.8"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
    "Cache-Control": "no-cache",
    "Pragma": "no-cache",
}

_playwright = None
_browser = None
_context = None


def clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", (text or "").strip())


def normalize_href(href: str) -> str:
    if not href:
        return ""
    if href.startswith("/"):
        return BASE_URL + href
    return href


def get_work_id_from_href(href: str) -> str:
    match = re.search(r"/books/(\d+)", href or "")
    return match.group(1) if match else ""


def get_browser_context():
    global _playwright, _browser, _context

    if _context is not None:
        return _context

    _playwright = sync_playwright().start()
    _browser = _playwright.chromium.launch(headless=True)
    _context = _browser.new_context(
        user_agent=HEADERS["User-Agent"],
        locale="ko-KR",
    )
    return _context


def close_browser_context():
    global _playwright, _browser, _context

    if _context is not None:
        _context.close()
        _context = None

    if _browser is not None:
        _browser.close()
        _browser = None

    if _playwright is not None:
        _playwright.stop()
        _playwright = None


atexit.register(close_browser_context)


def fetch_html_with_browser(url: str) -> str:
    context = get_browser_context()
    page = context.new_page()
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=30000)
        page.wait_for_timeout(1500)
        return page.content()
    finally:
        page.close()


def fetch_html(url: str) -> BeautifulSoup:
    try:
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()
        return BeautifulSoup(response.text, "html.parser")
    except requests.HTTPError as e:
        if getattr(e.response, "status_code", None) != 403:
            raise
    except requests.RequestException:
        pass

    html = fetch_html_with_browser(url)
    return BeautifulSoup(html, "html.parser")


def get_book_anchor(item):
    candidates = []

    for anchor in item.find_all("a", href=True):
        href = anchor.get("href", "")
        text = clean_text(anchor.get_text(" ", strip=True))
        if "/books/" not in href:
            continue
        candidates.append((anchor, text))

    text_candidates = [entry for entry in candidates if entry[1] and entry[1].lower() != "image"]
    if text_candidates:
        return text_candidates[0][0]

    if candidates:
        return candidates[0][0]

    return None


def get_card_candidates(soup) -> List[Any]:
    cards_by_work_id: Dict[str, Any] = {}
    card_order: List[str] = []

    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        title = clean_text(anchor.get_text(" ", strip=True))
        if "/books/" not in href or not title or title.lower() == "image":
            continue

        card = None
        for parent in anchor.parents:
            if getattr(parent, "name", None) != "li":
                continue
            item_text = clean_text(parent.get_text(" ", strip=True))
            if title not in item_text:
                continue
            if not re.search(r"총\s*[\d,]+\s*화", item_text):
                continue
            card = parent
            break

        if card is None:
            continue

        work_url = normalize_href(href)
        work_id = get_work_id_from_href(work_url) or work_url
        existing = cards_by_work_id.get(work_id)
        if existing is None:
            cards_by_work_id[work_id] = card
            card_order.append(work_id)
            continue

        # Prefer the explicit ranked-list link over duplicated featured cards.
        if "_rdt_idx=" in href and "_rdt_idx=" not in clean_text(existing.get("data-codex-href", "")):
            card["data-codex-href"] = href
            cards_by_work_id[work_id] = card

    cards = [cards_by_work_id[work_id] for work_id in card_order]
    for card in cards:
        if not card.get("data-codex-href"):
            anchor = get_book_anchor(card)
            if anchor:
                card["data-codex-href"] = anchor.get("href", "")

    return cards


def get_anchor_texts(item, exclude_href: str) -> List[str]:
    texts = []

    for anchor in item.find_all("a", href=True):
        href = normalize_href(anchor.get("href", ""))
        text = clean_text(anchor.get_text(" ", strip=True))
        if not text or text.lower() == "image":
            continue
        if href == exclude_href:
            continue
        texts.append(text)

    deduped = []
    for text in texts:
        if text not in deduped:
            deduped.append(text)
    return deduped


def get_card_lines(item) -> List[str]:
    lines = []
    for line in item.get_text("\n", strip=True).splitlines():
        cleaned = clean_text(line)
        if not cleaned or cleaned.lower() == "image":
            continue
        lines.append(cleaned)
    return lines


def get_book_url_map(soup) -> Dict[str, str]:
    mapping: Dict[str, str] = {}
    for anchor in soup.find_all("a", href=True):
        href = anchor.get("href", "")
        title = clean_text(anchor.get_text(" ", strip=True))
        if "/books/" not in href or not title or title.lower() == "image":
            continue
        mapping.setdefault(title, normalize_href(href))
    return mapping


def extract_metadata_parts(meta_line: str):
    parts = meta_line.split()
    if len(parts) >= 3:
        return parts[0], parts[1], " ".join(parts[2:])
    if len(parts) == 2:
        return parts[0], parts[1], "-"
    if len(parts) == 1:
        return parts[0], "-", "-"
    return "-", "-", "-"


def parse_ranked_entries(soup, category_key: str) -> List[Dict[str, str]]:
    lines = [clean_text(line) for line in soup.get_text("\n").splitlines()]
    lines = [line for line in lines if line]
    book_url_map = get_book_url_map(soup)

    entries: List[Dict[str, str]] = []
    seen_titles = set()

    for index, line in enumerate(lines):
        stats_match = re.match(r"^총\s*([\d,]+)\s*화\s*([0-9.]+)\(([\d,]+)\)", line)
        if not stats_match or index < 2:
            continue

        title = lines[index - 2]
        if title in seen_titles:
            continue

        author, publisher, genre = extract_metadata_parts(lines[index - 1])
        work_url = book_url_map.get(title, "")
        if not work_url:
            continue

        rank_value = f"{len(entries) + 1}위"
        for probe in range(index + 1, min(index + 4, len(lines))):
            if re.fullmatch(r"\d{1,3}", lines[probe]):
                rank_value = f"{int(lines[probe])}위"
                break

        entries.append(
            {
                "category": category_key,
                "title": title,
                "author": author,
                "publisher": publisher,
                "genre": genre or category_key,
                "totalEpisodes": f"{stats_match.group(1)}화",
                "rating": stats_match.group(2),
                "ridi_rating_count": stats_match.group(3),
                "rank": rank_value,
                "url": work_url,
            }
        )
        seen_titles.add(title)

    return entries


def parse_entries_from_cards(cards: List[Any], category_key: str) -> List[Dict[str, str]]:
    entries: List[Dict[str, str]] = []
    seen_titles = set()

    for idx, card in enumerate(cards, start=1):
        anchor = get_book_anchor(card)
        if not anchor:
            continue

        title = clean_text(anchor.get_text(" ", strip=True))
        work_url = normalize_href(anchor.get("href", ""))
        if not title or not work_url or title in seen_titles:
            continue

        card_lines = get_card_lines(card)
        item_text = clean_text(" ".join(card_lines))
        anchor_texts = get_anchor_texts(card, work_url)
        author = anchor_texts[0] if len(anchor_texts) >= 1 else "-"
        publisher = anchor_texts[1] if len(anchor_texts) >= 2 else "-"
        genre = extract_genre(item_text, title, author, publisher, category_key)
        total_episodes, rating, ridi_rating_count = extract_series_stats(item_text)
        rank_value = extract_rank(idx)

        entries.append(
            {
                "category": category_key,
                "title": title,
                "author": author,
                "publisher": publisher,
                "genre": genre,
                "totalEpisodes": total_episodes,
                "rating": rating,
                "ridi_rating_count": ridi_rating_count,
                "rank": rank_value,
                "url": work_url,
            }
        )
        seen_titles.add(title)

    return entries


def extract_rank(fallback_rank: int) -> str:
    return f"{fallback_rank}위"


def extract_series_stats(item_text: str):
    total_episodes = "-"
    rating = "-"
    rating_count = "-"

    total_match = re.search(r"총\s*([\d,]+)\s*화", item_text)
    if total_match:
        total_episodes = f"{total_match.group(1)}화"

    rating_match = re.search(r"총\s*[\d,]+\s*화\s*([0-9.]+)\s*\(\s*([\d,]+)\s*\)", item_text)
    if not rating_match:
        rating_match = re.search(r"([0-9.]+)\s*\(\s*([\d,]+)\s*\)", item_text)
    if rating_match:
        rating = rating_match.group(1)
        rating_count = rating_match.group(2)

    return total_episodes, rating, rating_count


def split_metadata_text(item_text: str, title: str, author: str, publisher: str) -> str:
    normalized = item_text
    if title:
        normalized = normalized.replace(title, "", 1).strip()
    if author and author != "-":
        normalized = normalized.replace(author, "", 1).strip()
    if publisher and publisher != "-":
        normalized = normalized.replace(publisher, "", 1).strip()
    return normalized


def extract_genre(item_text: str, title: str, author: str, publisher: str, category_key: str) -> str:
    metadata_text = split_metadata_text(item_text, title, author, publisher)
    match = re.search(r"^(.*?)\s+총\s*[\d,]+\s*화", metadata_text)
    if match:
        genre = clean_text(match.group(1))
        if genre:
            return genre
    return category_key


def build_promotion(item, item_text: str) -> Optional[Dict[str, Any]]:
    labels = []
    for node in item.select("[aria-label]"):
        label = clean_text(node.get("aria-label", ""))
        if label and label not in labels:
            labels.append(label)

    if not labels:
        return None

    combined = " ".join(labels)
    time_free_type = "none"
    if "리다무" in combined or "기다리면 무료" in combined:
        time_free_type = "waitFree"
    elif "시간" in combined and "무료" in combined:
        time_free_type = "threeHour"

    free_episodes = None
    free_match = re.search(r"(\d+)\s*화\s*무료", combined)
    if free_match:
        free_episodes = int(free_match.group(1))

    return {
        "timeFreeType": time_free_type,
        "tag": combined,
        "freeEpisodes": free_episodes,
        "daysLeft": None,
        "eventBanners": [],
        "notices": [],
        "benefits": [],
        "ridiWaitFree": time_free_type == "waitFree",
        "ridiFreeLabel": free_match.group(0) if free_match else None,
        "ridiWaitFreeText": None,
        "serialSchedule": None,
        "exclusiveText": None,
    }


def parse_list(list_url: str, category_key: str) -> List[Dict[str, Any]]:
    soup = fetch_html(list_url)
    cards = get_card_candidates(soup)
    card_by_title = {}
    for card in cards:
        card_anchor = get_book_anchor(card)
        if not card_anchor:
            continue
        card_title = clean_text(card_anchor.get_text(" ", strip=True))
        if card_title and card_title not in card_by_title:
            card_by_title[card_title] = card

    ranked_entries = parse_entries_from_cards(cards, category_key)
    if not ranked_entries:
        ranked_entries = parse_ranked_entries(soup, category_key)
    results = []

    for entry in ranked_entries:
        title = entry["title"]
        work_url = entry["url"]
        card = card_by_title.get(title)
        item_text = clean_text(card.get_text(" ", strip=True)) if card else ""
        promotion = build_promotion(card, item_text) if card else None

        work_id_match = re.search(r"/books/(\d+)", work_url)
        work_id = work_id_match.group(1) if work_id_match else ""

        result = {
            "category": entry["category"],
            "카테고리": entry["category"],
            "rank": entry["rank"],
            "is_promotion": entry["rank"] == "프로모션",
            "title": title,
            "author": entry["author"],
            "publisher": entry["publisher"],
            "출판사": entry["publisher"],
            "genre": entry["genre"],
            "totalEpisodes": entry["totalEpisodes"],
            "rating": entry["rating"],
            "ridi_rating_count": entry["ridi_rating_count"],
            "thumbnail": f"https://img.ridicdn.net/cover/{work_id}/large#1" if work_id else "-",
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
            print(f"RIDI_CATEGORY {key}: {len(items)}")
            for sample in items[:3]:
                print(
                    "RIDI_SAMPLE "
                    f"{key} | title={sample.get('title', '-')} | "
                    f"author={sample.get('author', '-')} | "
                    f"publisher={sample.get('publisher', '-')} | "
                    f"rank={sample.get('rank', '-')} | "
                    f"episodes={sample.get('totalEpisodes', '-')} | "
                    f"ratingCount={sample.get('ridi_rating_count', '-')}"
                )
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
    for item in items[:10]:
        if item.get("promotion"):
            print("PROMO:", item["category"], item["title"], "=>", item["promotion"])
    save_ridi_promotions_json(items)
