from pymongo import MongoClient, UpdateOne
import requests
import os
from dotenv import load_dotenv

# [환경 설정]
load_dotenv()
GOV_API_KEY = os.getenv('GOV_API_KEY')
SNS_API_URL = os.getenv('SNS_API_URL')
MONGO_URI = os.getenv('MONGO_URI')

client = MongoClient(MONGO_URI)
db = client['assembly_insight']
members_col = db['members']

def sync_22nd_sns_to_db():
    print("🎯 22대 SNS 데이터 DB 동기화 시작 (SNS_INFO 전용)...")

    params = {'KEY': GOV_API_KEY, 'Type': 'json', 'pIndex': 1, 'pSize': 500}
    
    try:
        response = requests.get(SNS_API_URL, params=params)
        data = response.json()
        
        # API 응답 구조 확인 및 데이터 추출
        if 'negnlnyvatsjwocar' not in data:
            print("❌ SNS API 응답에 데이터가 없습니다.")
            return
            
        sns_rows = data['negnlnyvatsjwocar'][1]['row']
        
        operations = []
        for row in sns_rows:
            # [필요 없는 PHOTO_PATH 생성 부분 제거]
            # 오직 SNS 정보와 22대 여부만 업데이트합니다.
            operations.append(
                UpdateOne(
                    {"NAAS_CD": row['MONA_CD']}, # 마스터 DB의 코드와 매칭
                    {"$set": {
                        "SNS_INFO": {
                            "facebook": row.get('F_URL'),
                            "youtube": row.get('Y_URL'),
                            "twitter": row.get('T_URL'),
                            "blog": row.get('B_URL')
                        },
                        "is_22nd": True # 22대 활동 의원 마킹
                    }},
                    upsert=False # 마스터 DB에 의원이 이미 있는 경우만 갱신
                )
            )
        
        if operations:
            result = members_col.bulk_write(operations, ordered=False)
            print(f"✅ 동기화 완료: {result.modified_count}명의 SNS 정보가 업데이트되었습니다.")

    except Exception as e:
        print(f"❌ 오류 발생: {e}")

if __name__ == "__main__":
    sync_22nd_sns_to_db()