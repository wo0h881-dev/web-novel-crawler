import requests
from bs4 import BeautifulSoup
import json
import os
import datetime

def fetch_kakao_ranking():
    # 카카오페이지 실시간 웹소설 랭킹
    url = "https://page.kakao.com/menu/11/screen/37"
    
    # 브라우저인 척 속이는 헤더 (매우 중요)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 카카오페이지 아이템을 찾는 최신 셀렉터 (구조적 접근)
        items = soup.find_all('div', class_=lambda x: x and 'flex-col' in x)
        
        results = []
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        count = 0
        for item in items:
            # p 태그 중 굵은 글씨(제목)와 일반 글씨(작가)를 찾음
            p_tags = item.find_all('p')
            if len(p_tags) >= 2:
                title = p_tags[0].text.strip()
                author = p_tags[1].text.strip()
                
                # 순위나 '무료' 같은 키워드 제외 필터링
                if title and len(title) > 1 and "위" not in title and count < 20:
                    count += 1
                    results.append({
                        "rank": f"{count}위",
                        "title": title,
                        "author": author,
                        "date": today
                    })
        
        return results
    except Exception as e:
        print(f"❌ 수집 중 에러: {e}")
        return []

def send_to_google_sheet(data):
    # GitHub Secrets에 넣은 구글 앱스 스크립트 배포 URL
    WEBAPP_URL = os.environ.get("WEBAPP_URL") 
    
    if not WEBAPP_URL:
        print("❌ WEBAPP_URL이 설정되지 않았습니다.")
        return

    payload = {
        "source": "kakao",  # 구글 시트가 카카오 탭에 넣으라고 알려줌
        "data": json.dumps(data)
    }

    try:
        # 주소 뒤에 파라미터를 붙여서 전송
        response = requests.get(WEBAPP_URL, params=payload)
        print(f"📡 전송 결과: {response.text}")
    except Exception as e:
        print(f"❌ 전송 중 에러: {e}")

if __name__ == "__main__":
    print("🚀 카카오 자동 수집 시작...")
    ranking_data = fetch_kakao_ranking()
    
    if ranking_data:
        print(f"✅ {len(ranking_data)}개 수집 성공!")
        send_to_google_sheet(ranking_data)
    else:
        # 이 메시지가 뜨면 카카오가 접속을 완전히 막은 것임
        print("⚠️ 데이터를 찾지 못했습니다. 셀렉터 확인이 필요합니다.")
