import json
import os
import time
import re
from pymongo import MongoClient
from datetime import datetime, timedelta
from kiwipiepy import Kiwi  # KoNLPy 대신 사용
from collections import Counter
from dotenv import load_dotenv

# [1. 환경 설정 및 DB 연결]
load_dotenv()
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
EXPORT_DIR = "data_export"

# Kiwi 초기화 (사용자 사전 추가나 옵션 설정이 가능합니다)
kiwi = Kiwi()

# 분석 시 제외할 정치 도메인 불용어 (Kiwi는 분석 능력이 좋아 불용어를 줄여도 잘 작동합니다)
STOPWORDS = ['의원', '국회의원', '뉴스', '오늘', '기자', '정치', '국회', '지난', '오전', '오후', '때문', '대한', '관련', '영상', '채널', '금지', '무단', '배포', '재배포', '이번', '경우', '통해']

def get_news_trend(news_list):
    """최근 7일간의 날짜별 뉴스 개수 집계"""
    today = datetime.now().date()
    date_range = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    trend_dict = {d: 0 for d in date_range}
    
    for news in news_list:
        p_date = news.get('pubDate')
        if isinstance(p_date, datetime):
            p_date_str = p_date.date().isoformat()
        elif isinstance(p_date, str):
            p_date_str = p_date[:10]
        else:
            continue
            
        if p_date_str in trend_dict:
            trend_dict[p_date_str] += 1
            
    return {
        "labels": [d[5:] for d in date_range],
        "data": [trend_dict[d] for d in date_range]
    }

def format_mongo_data(data):
    """MongoDB 특수 객체를 표준 JSON 타입으로 변환"""
    if isinstance(data, list):
        return [format_mongo_data(item) for item in data]
    if isinstance(data, dict):
        new_dict = {}
        for k, v in data.items():
            if k == "_id":
                new_dict[k] = str(v)
            elif isinstance(v, datetime):
                new_dict[k] = v.isoformat()
            elif isinstance(v, (dict, list)):
                new_dict[k] = format_mongo_data(v)
            else:
                new_dict[k] = v
        return new_dict
    return data

def extract_member_keywords(news_list, video_list, member_name):
    """Kiwi를 사용한 고성능 핵심 키워드 추출"""
    raw_text = ""
    # 제목 가중치 부여 (2번 반복)
    for n in news_list: 
        raw_text += f" {n.get('title', '')*2} {n.get('description', '')}"
    for v in video_list: 
        raw_text += f" {v.get('title', '')*2} {v.get('description', '')}"
    
    if not raw_text.strip():
        return {"top_keywords": [], "keyword_details": []}

    # Kiwi 형태소 분석
    # NNG(일반 명사), NNP(고유 명사) 추출
    result = kiwi.tokenize(raw_text)
    
    # 2글자 이상 + 명사류 + 불용어 제외 + 의원 이름 제외
    nouns = [
        t.form for t in result 
        if t.tag in ['NNG', 'NNP'] and len(t.form) > 1 
        and t.form not in STOPWORDS 
        and t.form != member_name
    ]
    
    # 상위 15개 키워드 산출
    keyword_counts = Counter(nouns).most_common(15)
    return {
        "top_keywords": [word for word, count in keyword_counts],
        "keyword_details": [{"text": word, "value": count} for word, count in keyword_counts]
    }

def export_integrated_insight():
    if not os.path.exists(EXPORT_DIR):
        os.makedirs(EXPORT_DIR)
        print(f"📂 폴더 생성 완료: {EXPORT_DIR}")

    print(f"\n🚀 [START] 22대 국회 통합 분석 시스템 (Kiwi Engine)")
    print("=" * 80)
    
    # 1. 22대 의원 로드
    members = list(db.members.find({"is_22nd": True}))
    total_members = len(members)
    
    if total_members == 0:
        print("⚠️ [ERROR] DB에 22대 의원 데이터가 없습니다.")
        return

    # 메인 페이지용 전체 명단 저장
    with open(os.path.join(EXPORT_DIR, "members_all.json"), 'w', encoding='utf-8') as f:
        json.dump(format_mongo_data(members), f, ensure_ascii=False, indent=4)
    print(f"✅ [MAIN] members_all.json 생성 완료")

    start_time = time.time()

    # 2. 의원별 개별 분석 및 파일 생성
    for i, member in enumerate(members, 1):
        naas_cd = member.get('NAAS_CD')
        name = member.get('HG_NM') or member.get('NAAS_NM') # 필드명 대응
        
        if not naas_cd: continue

        print(f"📦 [{i}/{total_members}] 분석 중: {name} ({naas_cd})", end=" ", flush=True)

        # 데이터 취합
        news = list(db.news.find({"related_members": naas_cd}).sort("pubDate", -1).limit(30))
        videos = list(db.youtube_videos.find({"MONA_CD": naas_cd}).sort("upload_date", -1).limit(20))

        # AI 키워드 분석 실행 (Kiwi)
        analysis_res = extract_member_keywords(news, videos, name)

        # 데이터 구조화
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
        
        # 개별 JSON 저장
        file_path = os.path.join(EXPORT_DIR, f"{naas_cd}.json")
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(combined_data, f, ensure_ascii=False, indent=4)
        
        kw_str = ', '.join(analysis_res['top_keywords'][:3])
        print(f" -> ✅ 완료 ({kw_str})")

    duration = time.time() - start_time
    print("\n" + "=" * 80)
    print(f"🏁 [FINISH] 총 {total_members}명 분석 완료. 소요시간: {duration:.2f}초")

if __name__ == "__main__":
    export_integrated_insight()