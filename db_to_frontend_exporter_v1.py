import json
import os
import time
import re
from pymongo import MongoClient
from datetime import datetime, timedelta
from konlpy.tag import Okt
from collections import Counter
from dotenv import load_dotenv

# [1. 환경 설정 및 DB 연결]
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
EXPORT_DIR = "data_export"
okt = Okt()

# 분석 시 제외할 정치 도메인 불용어
STOPWORDS = ['의원', '국회의원', '뉴스', '오늘', '기자', '정치', '국회', '지난', '오전', '오후', '때문', '대한', '관련', '영상', '채널', '금지', '무단', '배포', '재배포', '명']

def get_news_trend(news_list):
    """최근 7일간의 날짜별 뉴스 개수 집계"""
    today = datetime.now().date()
    # 최근 7일 날짜 리스트 생성 (오늘 포함)
    date_range = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    
    # 초기값 세팅 { "2026-01-06": 0, "2026-01-07": 0 ... }
    trend_dict = {d: 0 for d in date_range}
    
    for news in news_list:
        # 뉴스 날짜 추출 (이미 ISO 문자열 또는 datetime 객체인 경우)
        p_date = news.get('pubDate')
        if isinstance(p_date, datetime):
            p_date_str = p_date.date().isoformat()
        else:
            p_date_str = p_date[:10] # "2026-01-12T..." 에서 앞 10자만 추출
            
        if p_date_str in trend_dict:
            trend_dict[p_date_str] += 1
            
    # Chart.js에서 쓰기 편하게 리스트 형태로 반환
    return {
        "labels": [d[5:] for d in date_range], # "01-06" 형태로 월-일만 표시
        "data": [trend_dict[d] for d in date_range]
    }

def format_mongo_data(data):
    """
    MongoDB 특수 객체($date, $oid)를 표준 JSON 타입으로 변환(평탄화)
    프론트엔드에서 new Date()로 바로 파싱 가능하게 함
    """
    if isinstance(data, list):
        return [format_mongo_data(item) for item in data]
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            if k == "_id":
                new_dict[k] = str(v)
            elif isinstance(v, datetime):
                # ISO 8601 문자열로 변환 (예: 2026-01-12T18:00:00)
                new_dict[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                new_dict[k] = format_mongo_data(v)
            else:
                new_dict[k] = v
        return new_dict
    return data

def extract_member_keywords(news_list, video_list, member_name):
    """뉴스/영상 텍스트에서 AI 핵심 키워드 추출"""
    raw_text = ""
    # 제목의 중요도가 높으므로 제목은 2번 반복하여 가중치 부여
    for n in news_list: 
        raw_text += f" {n.get('title', '')*2} {n.get('description', '')}"
    for v in video_list: 
        raw_text += f" {v.get('title', '')*2} {v.get('description', '')}"
    
    # 한글, 영문, 숫자만 추출
    clean_text = re.sub(r'[^가-힣a-zA-Z0-9\s]', '', raw_text)
    nouns = okt.nouns(clean_text)
    
    # 2글자 이상 + 불용어 제외 + 의원 성함 제외
    filtered_nouns = [n for n in nouns if len(n) > 1 and n not in STOPWORDS and n != member_name]
    
    # 상위 15개 키워드 산출
    keyword_counts = Counter(filtered_nouns).most_common(15)
    return {
        "top_keywords": [word for word, count in keyword_counts],
        "keyword_details": [{"text": word, "value": count} for word, count in keyword_counts]
    }

def export_integrated_insight():
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)
        print(f"📂 폴더 생성 완료: {EXPORT_DIR}")

    print(f"\n🚀 [START] 22대 국회 통합 분석 및 JSON 스냅샷 생성 시작")
    print("=" * 80)
    
    # 1. 대상 의원 로드
    members = list(db.members.find({"is_22nd": True}))
    total_members = len(members)
    
    if total_members == 0:
        print("⚠️ [ERROR] DB에 22대 의원 데이터가 없습니다.")
        return

    # 메인 페이지용 전체 명단 저장 (평탄화 적용)
    with open(os.path.join(EXPORT_DIR, "members_all.json"), 'w', encoding='utf-8') as f:
        json.dump(format_mongo_data(members), f, ensure_ascii=False, indent=4)
    print(f"✅ [MAIN] members_all.json 생성 완료")

    start_time = time.time()

    # 2. 의원별 개별 분석 및 파일 생성
    for i, member in enumerate(members, 1):
        naas_cd = member.get('NAAS_CD')
        name = member.get('NAAS_NM')
        
        if not naas_cd: continue

        print(f"📦 [{i}/{total_members}] 분석 중: {name} ({naas_cd})", end=" ", flush=True)

        # Step 1: 데이터 취합 (최신순 정렬 및 데이터 평탄화)
        news = list(db.news.find({"related_members": naas_cd}).sort("pubDate", -1).limit(20))
        videos = list(db.youtube_videos.find({"MONA_CD": naas_cd}).sort("upload_date", -1).limit(10))

        # Step 2: AI 키워드 분석 실행
        analysis_res = extract_member_keywords(news, videos, name)

        # Step 3: 데이터 구조화 및 날짜 평탄화 적용
        combined_data = {
            "profile": format_mongo_data(member),
            "analysis": {
                "keywords": analysis_res["top_keywords"],
                "keyword_frequency": analysis_res["keyword_details"],
                "last_analyzed_at": datetime.now().isoformat(),
                "trend_news": get_news_trend(news),
            },
            "recent_news": format_mongo_data(news),
            "recent_videos": format_mongo_data(videos),
            "exported_at": datetime.now().isoformat()
        }
        
        # Step 4: 개별 JSON 저장 (json_util 대신 일반 json 사용)
        file_path = os.path.join(EXPORT_DIR, f"{naas_cd}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=4)
        
        print(f" -> ✅ 분석 완료 (키워드: {', '.join(analysis_res['top_keywords'][:3])}...)")

    duration = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"🏁 [FINISH] 총 {total_members}명의 통합 데이터 생성이 완료되었습니다. ({duration:.2f}초)")

if __name__ == "__main__":
    export_integrated_insight()