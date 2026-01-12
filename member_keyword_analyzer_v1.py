import json
from pymongo import MongoClient
from konlpy.tag import Okt
from collections import Counter
import re
from datetime import datetime
import time

# MongoDB 접속 설정
# 1. MongoDB 접속
MONGO_URI = "mongodb+srv://irotwins_db_user:irontwins!pw@cluster0.x1qcqgj.mongodb.net/?appName=Cluster0"
client = MongoClient(MONGO_URI)
db = client['assembly_insight']
okt = Okt()

# 불용어 정의
STOPWORDS = ['의원', '국회의원', '뉴스', '오늘', '기자', '정치', '국회', '지난', '오전', '오후', '때문', '대한', '관련', '영상', '채널']

def extract_keywords_with_logging():
    # 1. 대상 의원 로드
    target_names = ["이재명", "김민석", "정청래", "우원식", "김병기", "조정식", "추미애", "우상호", "홍영표", "정성호", "주호영", "조경태", "이철규", "김기현", "안철수", "박찬대", "박홍근", "홍익표", "윤호중", "한동훈", "이준석", "천하람", "강훈식", "인요한", "김성회"]
    members = list(db.members.find({"HG_NM": {"$in": target_names}}))
    
    total_members = len(members)
    print(f"\n🚀 [START] 총 {total_members}명의 의원에 대한 키워드 분석을 시작합니다.")
    print("=" * 70)

    start_time = time.time()

    for i, member in enumerate(members, 1):
        name = member['HG_NM']
        mona_cd = member['MONA_CD']
        
        print(f"\n📊 [{i}/{total_members}] 의원 분석 중: {name} ({mona_cd})")
        print("-" * 40)

        # Step 1: 데이터 취합
        print(f"   Step 1: 텍스트 수집 중...", end=" ", flush=True)
        news_docs = list(db.news.find({"MONA_CD": mona_cd}))
        video_docs = list(db.videos.find({"MONA_CD": mona_cd}))
        
        raw_text = ""
        for n in news_docs: raw_text += f" {n['title']} {n.get('description', '')}"
        for v in video_docs: raw_text += f" {v['title']} {v.get('description', '')}"
        
        print(f"✅ (뉴스 {len(news_docs)}건, 영상 {len(video_docs)}건 취합 완료)")

        # Step 2: 전처리 및 명사 추출
        print(f"   Step 2: 자연어 처리(NLP) 분석 중...", end=" ", flush=True)
        clean_text = re.sub(r'[^\w\s]', '', raw_text)
        nouns = okt.nouns(clean_text)
        print(f"✅ (총 {len(nouns)}개의 명사 식별)")

        # Step 3: 필터링 및 빈도 계산
        print(f"   Step 3: 키워드 정제 및 가중치 계산...", end=" ", flush=True)
        filtered_nouns = [n for n in nouns if len(n) > 1 and n not in STOPWORDS and n != name]
        keyword_counts = Counter(filtered_nouns).most_common(20)
        top_10_preview = [word for word, count in keyword_counts[:10]]
        print(f"✅")

        # Step 4: 결과 DB 업데이트
        print(f"   Step 4: 분석 결과 DB 반영 중...", end=" ", flush=True)
        db.members.update_one(
            {"MONA_CD": mona_cd},
            {"$set": {
                "top_keywords": [word for word, count in keyword_counts],
                "keyword_frequency": dict(keyword_counts), # 빈도수도 함께 저장 (워드클라우드용)
                "last_analyzed_at": datetime.now()
            }}
        )
        print(f"✅")

        # 결과 요약 출력
        print(f"   💡 핵심 키워드: {', '.join(top_10_preview)}")
        
    end_time = time.time()
    duration = end_time - start_time
    print("\n" + "=" * 70)
    print(f"🏁 [FINISH] 모든 분석이 완료되었습니다. (소요시간: {duration:.2f}초)")
    print(f"📂 결과는 MongoDB 'members' 컬렉션의 'top_keywords' 필드에 저장되었습니다.")

if __name__ == "__main__":
    extract_keywords_with_logging()