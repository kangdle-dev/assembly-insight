import requests
import json
import os
import sys
import urllib3
from PIL import Image
from io import BytesIO
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv

# .env 로드 (보안 관리)
load_dotenv()

# SSL 경고 무시
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# [설정] 환경변수 사용
API_KEY = os.getenv("GOV_API_KEY")
MONGO_URI = os.getenv("MONGO_URI")
IMAGE_DIR = 'all_member_photos'
THUMB_DIR = 'member_thumbs_300' 

# MongoDB 연결
client = MongoClient(MONGO_URI)
db = client['assembly_insight']
members_col = db['members']

def setup_db():
    """중복 방지 및 빠른 집계를 위한 인덱스 최적화"""
    members_col.create_index("NAAS_CD", unique=True)
    members_col.create_index("CURR_PLPT_NM")
    members_col.create_index("is_22nd")
    print("✅ MongoDB 인덱스 설정 및 최적화 완료")

def fetch_to_mongodb():
    """API 데이터를 수집하여 정제 및 최적화 후 MongoDB에 저장"""
    p_index, p_size = 1, 100
    total_upserted = 0
    
    # 삭제 대상 원시 필드 목록 (정제 후 필요 없는 데이터)
    FIELDS_TO_DROP = ["ELECD_NM", "PLPT_NM", "GTELT_ERACO", "ELECD_DIV_NM"]

    print("🚀 국회 API -> MongoDB 데이터 수집/정제/최적화 가동...")

    while True:
        params = {'KEY': API_KEY, 'Type': 'json', 'pIndex': p_index, 'pSize': p_size}
        try:
            response = requests.get("https://open.assembly.go.kr/portal/openapi/ALLNAMEMBER", params=params)
            data = response.json()
            
            if 'ALLNAMEMBER' in data:
                rows = data['ALLNAMEMBER'][1]['row']
                
                operations = []
                for row in rows:
                    # 1. 기초 데이터 확보 및 None 방어
                    raw_units = row.get('GTELT_ERACO') or ""  
                    raw_parties = row.get('PLPT_NM') or ""   
                    raw_districts = row.get('ELECD_NM') or "" 

                    # 2. 리스트화 및 숫자 기수 파싱 (에러 방어)
                    unit_list = []
                    for u in raw_units.split(','):
                        u_strip = u.strip()
                        if not u_strip: continue
                        digits = ''.join(filter(str.isdigit, u_strip))
                        if digits: unit_list.append(int(digits))

                    party_list = [p.strip() for p in raw_parties.split('/') if p.strip()]
                    district_list = [d.strip() for d in raw_districts.split('/') if d.strip()]

                    # 3. HISTORY_TIMELINE 매핑 (기수/정당/지역구 1:1 매칭)
                    timeline = []
                    for unit, party, dist in zip(unit_list, party_list, district_list):
                        timeline.append({
                            "unit": unit,       
                            "party": party,     
                            "district": dist    
                        })

                    # 4. 정제 필드 생성
                    row['HISTORY_TIMELINE'] = timeline
                    row['CURR_PLPT_NM'] = timeline[-1]['party'] if timeline else "무소속"
                    row['CURR_ELECD_NM'] = timeline[-1]['district'] if timeline else "미정"
                    
                    # 당선 횟수 산출 (타임라인 우선, 없을 시 텍스트 기반 추출)
                    if timeline:
                        row['RLCT_COUNT'] = len(timeline)
                    else:
                        rlct_str = row.get('RLCT_DIV_NM') or ""
                        digits_rlct = ''.join(filter(str.isdigit, rlct_str))
                        row['RLCT_COUNT'] = int(digits_rlct) if digits_rlct else 1

                    # 5. [중요] 불필요한 원시 필드 제거 (데이터 최적화)
                    for field in FIELDS_TO_DROP:
                        if field in row:
                            del row[field]

                    # 6. Bulk Write 준비
                    operations.append(
                        UpdateOne(
                            {"NAAS_CD": row['NAAS_CD']},
                            {"$set": row},
                            upsert=True
                        )
                    )
                
                if operations:
                    members_col.bulk_write(operations)
                    total_upserted += len(rows)
                    print(f"📦 {p_index}페이지 수집 및 최적화 완료: {len(rows)}명")
                
                if len(rows) < p_size: break
                p_index += 1
            else: break
        except Exception as e:
            print(f"❌ 수집 중 오류 발생: {e}")
            break
            
    print(f"💾 MongoDB 반영 및 스키마 최적화 완료! (총 {total_upserted}명)")

def process_images_and_update_path():
    """
    이미지 다운로드 없이, 로컬 파일 존재 여부만 확인하여 
    DB의 PHOTO_PATH 필드를 표준화된 경로로 일괄 업데이트합니다.
    """
    # 1. DB에서 전체 의원 목록 가져오기
    members = list(members_col.find({}, {"NAAS_CD": 1, "NAAS_NM": 1, "HG_NM": 1}))
    total = len(members)
    updated_count = 0
    missing_files = 0
    db_updates = []

    print(f"\n🚀 총 {total}명의 이미지 경로 DB 업데이트를 시작합니다.")
    print(f"📂 기준 폴더: ./{THUMB_DIR}")
    print("-" * 70)

    for index, member in enumerate(members, 1):
        code = member.get('NAAS_CD')
        name = member.get('NAAS_NM') or member.get('HG_NM')
        
        # 표준화된 썸네일 파일명 및 상대 경로 정의
        thumb_filename = f"{name}_{code}_300.jpg"
        thumb_local_path = os.path.join(THUMB_DIR, thumb_filename)
        
        # 프론트엔드에서 참조할 웹 경로 (상대 경로)
        relative_path = f"{THUMB_DIR}/{thumb_filename}"

        # 실제 로컬에 파일이 있는지 체크 (선택 사항이나 정합성을 위해 권장)
        if os.path.exists(thumb_local_path):
            # DB 업데이트 리스트 추가
            db_updates.append(
                UpdateOne(
                    {"NAAS_CD": code},
                    {"$set": {"PHOTO_PATH": relative_path}}
                )
            )
            updated_count += 1
        else:
            missing_files += 1

        # 진행 상황 표시
        if index % 100 == 0 or index == total:
            sys.stdout.write(f"\r🔄 진행 중: {index}/{total} (파일 확인 중...)")
            sys.stdout.flush()

        # 500건마다 DB 벌크 업데이트 실행 (성능 최적화)
        if len(db_updates) >= 500:
            members_col.bulk_write(db_updates, ordered=False)
            db_updates = []

    # 남은 업데이트 처리
    if db_updates:
        members_col.bulk_write(db_updates, ordered=False)

    print(f"\n\n🏁 경로 업데이트 완료 리포트")
    print(f"✅ PHOTO_PATH 갱신 완료: {updated_count}명")
    print(f"⚠️ 로컬 파일 없음 (건너뜀): {missing_files}명")
    print("-" * 70)

if __name__ == "__main__":
    setup_db()
    # fetch_to_mongodb()
    process_images_and_update_path() # 이미지 처리는 필요 시 주석 해제