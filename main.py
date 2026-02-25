import requests
from bs4 import BeautifulSoup
import json
import os
import datetime

def fetch_kakao_ranking():
    # 카카오페이지 실시간 랭킹 주소 (웹소설)
    url = "https://page.kakao.com/menu/11/screen/37"
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    }

    try:
        response = requests.get(url, headers=headers)
        # 한글 깨짐 방지
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # 카카오페이지의 일반적인 리스트 아이템 구조 (구조 변경 시 확인 필요)
        items = soup.select('div[class*="flex-col"]') 
        
        results = []
        today = datetime.datetime.now().strftime("%Y-%m-%d")

        count = 0
        for item in items:
            # 제목과 작가가 포함된 태그 찾기
            title_elem = item.select_one('p[class*="font-bold"]') 
            author_elem = item.select_one('p[class*="text-el-60"]') 
            
            if title_elem and count < 20:
                count += 1
                results.append({
                    "rank": f"{count}위",
                    "title": title_elem.text.strip(),
                    "author": author_elem.text.strip() if author_elem else "작가미상",
                    "date": today
                })
        
        return results
    except Exception as e:
        print(f"❌ 데이터 수집 중 오류 발생: {e}")
        return []

def send_to_google_sheet(data):
    # 깃허브 Secrets에 저장한 WEBAPP_URL 값을 불러옵니다.
    # 코드에 직접 주소를 적지 않아도 보안상 안전하게 전송됩니다.
    WEBAPP_URL = os.environ.get("WEBAPP_URL") 
    
    if not WEBAPP_URL:
        print("❌ 에러: WEBAPP_URL 환경변수가 설정되지 않았습니다.")
        return

    # 전송 데이터 구성 (중앙 관제 시트에서 카카오임을 식별하도록 source 설정)
    payload = {
        "source": "kakao",
        "data": json.dumps(data)
    }

    try:
        # GET 방식으로 구글 웹앱(GAS)에 데이터 전송
        response = requests.get(WEBAPP_URL, params=payload)
        print(f"📡 전송 시도... 결과: {response.text}")
    except Exception as e:
        print(f"❌ 데이터 전송 중 오류 발생: {e}")

if __name__ == "__main__":
    print("🚀 [카카오페이지] 랭킹 수집 및 전송 시작...")
    ranking_data = fetch_kakao_ranking()
    
    if ranking_data:
        print(f"✅ {len(ranking_data)}개의 데이터를 성공적으로 긁어왔습니다.")
        send_to_google_sheet(ranking_data)
    else:
        print("⚠️ 수집된 데이터가 없습니다. 셀렉터(Selector)를 확인해주세요.")
