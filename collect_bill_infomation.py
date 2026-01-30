import requests
import os
import time
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv
import urllib3

load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 1. DB 및 설정 로드
API_KEY = os.getenv("GOV_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
BILL_URL = "https://open.assembly.go.kr/portal/openapi/nzmimeepazxkubdpn"

client = MongoClient(MONGO_URI)
db = client['assembly_insight']
# 의원 기본 정보가 저장된 컬렉션 (이미 수집되었다고 하신 곳)
members_col = db['members'] 
# 정책 데이터를 저장할 컬렉션
policy_col = db['members_policy']

def collect_all_members_bills():
    # 2. 수집해야 할 의원 목록 가져오기
    # (예: 이름 필드만 추출)
    member_list = list(members_col.find({"is_22nd":True}, {"NAAS_NM": 1, "_id": 0}))
    total_members = len(member_list)
    print(f"📊 총 {total_members}명의 의원 목록을 확인했습니다. 수집을 시작합니다.")

    for idx, member in enumerate(member_list):
        name = member['NAAS_NM']
        print(f"\n[{idx+1}/{total_members}] {name} 의원 수집 중...")
        
        # 앞서 만든 fetch_all_and_details 로직 실행
        all_bills = fetch_bills_logic(name)
        
        if all_bills:
            policy_col.update_one(
                {"name": name},
                {
                    "$set": {
                        "representative_bills": all_bills,
                        "total_count": len(all_bills),
                        "last_updated": datetime.now()
                    }
                },
                upsert=True
            )
            print(f"✅ {name} 의원: {len(all_bills)}건 저장 완료")
        
        # API 과부하 방지 및 차단 예방 (0.5초 대기)
        time.sleep(0.5)

def fetch_bills_logic(member_name):
    """실제 API 호출 및 페이지네이션 처리 함수"""
    bills = []
    page = 1
    while True:
        params = {
            'KEY': API_KEY, 'Type': 'json', 'pIndex': page, 
            'pSize': 100, 'AGE': '22', 'PROPOSER': member_name
        }
        try:
            res = requests.get(BILL_URL, params=params, verify=False)
            data = res.json()
            if 'nzmimeepazxkubdpn' in data:
                rows = data['nzmimeepazxkubdpn'][1]['row']
                # 대표발의자 필터링
                filtered = [row for row in rows if member_name in row.get('RST_PROPOSER', '')]
                bills.extend(filtered)
                if len(rows) < 100: break
                page += 1
            else:
                break
        except:
            break
    return bills

if __name__ == "__main__":
    collect_all_members_bills()