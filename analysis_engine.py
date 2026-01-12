import pymongo
from konlpy.tag import Mecab
from collections import Counter
import json
import os
from dotenv import load_dotenv
from pymongo import MongoClient

# [환경 로드]
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

# 1. 환경 설정 및 경로 생성
EXPORT_DIR = "data_export"
if not os.path.exists(EXPORT_DIR):
    os.makedirs(EXPORT_DIR)

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
news_col = db["news"]

def save_analysis_json(member_name):
    """
    특정 의원의 뉴스를 분석하여 JSON 파일로 저장합니다.
    파일명: data_export/analysis_{member_name}.json
    """
    print(f"🚀 [{member_name}] 분석 및 JSON 생성 시작...")
    
    # 2. 데이터 쿼리 (최근 100건)
    cursor = news_col.find({
        "$or": [{"title": {"$regex": member_name}}, {"content": {"$regex": member_name}}]
    }).sort("pub_date", -1).limit(100)
    
    news_list = list(cursor)
    if not news_list:
        return print("⚠️ 데이터가 부족하여 분석을 중단합니다.")

    # 3. 분석 로직 (제목 가중치 3배)
    mecab = Mecab()
    weighted_text = ""
    for news in news_list:
        weighted_text += (news.get('title', '') + " ") * 3 + news.get('content', '')[:200]

    stopwords = [member_name, '의원', '국회', '정치', '오늘', '기자', '뉴스', '발언', '논란']
    nouns = [n for n in mecab.nouns(weighted_text) if len(n) > 1 and n not in stopwords]
    
    # 4. JSON 구조 설계
    top_keywords = Counter(nouns).most_common(15)
    analysis_result = {
        "member_name": member_name,
        "last_updated": "2026-01-12 08:50", # 실제로는 datetime.now() 사용
        "total_news_count": len(news_list),
        "keywords": [
            {"text": word, "value": count} for word, count in top_keywords
        ]
    }

    # 5. 파일 저장
    file_path = os.path.join(EXPORT_DIR, f"analysis_{member_name}.json")
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(analysis_result, f, ensure_ascii=False, indent=4)
    
    print(f"✅ 저장 완료: {file_path}")

# 테스트 실행
save_analysis_json("정청래")