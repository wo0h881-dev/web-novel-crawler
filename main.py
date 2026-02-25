import requests
from bs4 import BeautifulSoup
import json
import os
import datetime

def fetch_kakao_ranking():
    # 카카오페이지 실시간 웹소설 랭킹 API 또는 웹 페이지
    url = "https://page.kakao.com/menu/11/screen/37"
    headers = {
        "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7"
    }

    try:
        response = requests.get(url, headers=headers)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 최신 카카오페이지의 리스트 아이템을 찾는 더 넓은 범위의 셀렉터
        # 1. 텍스트가 들어있는 모든 div/p 태그를 탐색
        results = []
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        # 카카오는 'div' 안에 'p' 태그로 제목이 들어가는 경우가 많음
        # 특정 클래스명에 의존하지 않고 구조적 특징으로 찾습니다.
        items = soup.find_all('div', class_=lambda x: x and 'flex-col' in x)
        
        if not items:
            # 다른 구조일 경우 대비 (아이템 리스트 전체를 가져옴)
            items = soup.select('div > a > div')

        count = 0
        for item in items:
            # 텍스트가 있는 태그들 중 제목과 작가 추정
            paragraphs = item.find_all('p')
            if len(paragraphs) >= 2:
                title = paragraphs[0].text.strip()
                author = paragraphs[1].text.strip()
                
                # 순위나 '무료' 같은 단어는 제외하고 실제 제목 같은 것만 필터링
                if title and len(title) > 1 and count < 20:
                    count += 1
                    results.append({
                        "rank": f"{count}위",
                        "title": title,
                        "author": author,
                        "date": today
                    })
        
        return results
    except Exception as e:
        print(f"❌ 데이터 수집 중 오류: {e}")
        return []
