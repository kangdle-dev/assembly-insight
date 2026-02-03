import os
from pymongo import MongoClient
from datetime import datetime
from dotenv import load_dotenv

# .env 파일에서 환경 변수 로드
load_dotenv()

# 1. MongoDB 설정
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = 'assembly_insight'
COLLECTION_NAME = 'members_policy'

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
collection = db[COLLECTION_NAME]

def update_member_policy_stats(member_basic_info):
    member_name = member_basic_info.get('NAAS_NM')
    naas_cd = member_basic_info.get('NAAS_CD')
    
    """
    특정 의원의 법안 처리 결과(PROC_RESULT)를 카테고리별로 분류하고 
    성과 지표(achievement_rate)를 계산하여 저장합니다.
    """
    member_policy = collection.find_one({"naas_cd": naas_cd})
    
    if not member_policy or 'representative_bills' not in member_policy:        
        print(f"⚠️ {member_name} 의원의 법안 데이터가 존재하지 않습니다.")
        return

    bills = member_policy['representative_bills']
    
    # 통계 초기화
    stats = {
        "passed": 0,    # 입법 성공 (원안가결, 수정가결)
        "reflected": 0, # 정책 반영 (대안반영폐기, 수정안반영폐기)
        "pending": 0,   # 심사 중 (null, 빈값)
        "failed": 0,    # 실패/철회 (폐기, 철회)
        "total": len(bills)
    }

    # PROC_RESULT 기반 카테고리 매핑
    for bill in bills:
        result = bill.get('PROC_RESULT')
        
        # 1. 입법 성공
        if result in ['원안가결', '수정가결']:
            stats['passed'] += 1
        # 2. 정책 반영 (실질적 성과)
        elif result in ['대안반영폐기', '수정안반영폐기']:
            stats['reflected'] += 1
        # 3. 심사 중
        elif result in [None, '', 'null']:
            stats['pending'] += 1
        # 4. 실패 및 철회
        elif result in ['폐기', '철회']:
            stats['failed'] += 1

    # 성과율 계산 (가결 + 반영 건수 / 전체)
    if stats['total'] > 0:
        success_count = stats['passed'] + stats['reflected']
        stats['achievement_rate'] = round((success_count / stats['total'] * 100), 1)
    else:
        stats['achievement_rate'] = 0

    # 2. MongoDB 업데이트 (analysis_stats 필드 생성)
    collection.update_one(
        {"naas_cd": naas_cd},
        {
            "$set": {
                "name": member_name,
                "analysis_stats": stats,
                "stats_updated_at": datetime.now()
            }
        }
    )
    print(f"📈 {member_name} 완료: 성과율 {stats['achievement_rate']}% (총 {stats['total']}건)")

def main():
    # collection에 등록된 모든 의원 리스트 가져오기
    # members = collection.find({}, {"name": 1})
    all_members = db['members'].find({"is_22nd": True}, {"NAAS_NM": 1, "NAAS_CD": 1})
    
    print(f"🚀 총 {collection.count_documents({})}명의 의원 통계 업데이트를 시작합니다.")
    
    
    
    for m in all_members:
        update_member_policy_stats(m)
    
    print("\n✨ 모든 의원의 정책 통계 업데이트가 완료되었습니다.")

if __name__ == "__main__":
    main()