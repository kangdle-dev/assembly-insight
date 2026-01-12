import yt_dlp
import os
import urllib3
import time
import sys
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from datetime import datetime

# [기본 설정]
load_dotenv()
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

# 환경 변수 및 DB 연결
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")
client = MongoClient(MONGO_URI)
db = client[DB_NAME]
youtube_col = db['youtube_videos']
members_col = db['members']

# 뉴스 채널 리스트 (효율을 위해 핵심 채널로 압축)
NEWS_CHANNELS = ["KBS뉴스", "MBC뉴스", "SBS뉴스", "JTBC News", "YTN", "국회방송", "연합뉴스TV", "TV조선", "채널A", "MBN"]
START_DATE = '20240101'

def collect_all_22nd_youtube():
    # 1. 22대 의원 전체 가져오기
    query = {"is_22nd": True}
    projection = {"NAAS_NM": 1, "HG_NM": 1, "NAAS_CD": 1, "_id": 0}
    members = list(members_col.find(query, projection))
    
    total_members = len(members)
    print(f"🚀 22대 국회의원 전원({total_members}명) 유튜브 수집 시작...")

    ydl_opts = {
        'quiet': True,
        'extract_flat': True,
        'skip_download': True,
        'nocheckcertificate': True,
        'daterange': yt_dlp.utils.DateRange(START_DATE),
        'match_filter': yt_dlp.utils.match_filter_func("duration >= 60"), # 1분 이상으로 완화 (더 많은 영상 확보)
    }

    for index, member in enumerate(members, 1):
        name = member.get('NAAS_NM') or member.get('HG_NM')
        code = member.get('NAAS_CD')
        
        print(f"\n🔄 [{index}/{total_members}] {name} ({code}) 수집 중...")
        ops = []

        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            # 의원 이름으로 직접 검색 (채널 필터 없이 검색하여 수집량 증대)
            # 검색어 예: "국회의원 홍길동" 또는 "홍길동 인터뷰"
            search_queries = [f"ytsearch10:국회의원 {name}", f"ytsearch5:{name} 뉴스"]
            
            for query_str in search_queries:
                try:
                    info = ydl.extract_info(query_str, download=False)
                    if 'entries' in info:
                        for entry in info['entries']:
                            if entry and name in entry.get('title', ''):
                                vid_url = f"https://www.youtube.com/watch?v={entry.get('id')}"
                                ops.append(UpdateOne(
                                    {"url": vid_url},
                                    {"$set": {
                                        "MONA_CD": code,
                                        "HG_NM": name,
                                        "title": entry.get('title'),
                                        "url": vid_url,
                                        "upload_date": entry.get('upload_date'),
                                        "duration": entry.get('duration'),
                                        "collected_at": datetime.now()
                                    }},
                                    upsert=True
                                ))
                except: continue

        if ops:
            result = youtube_col.bulk_write(ops)
            print(f"   ㄴ ✅ 신규: {result.upserted_count} / 갱신: {result.modified_count}")
        
        # 300명 대량 수집이므로 차단 방지를 위해 0.5초~1초 대기
        time.sleep(0.5)

if __name__ == "__main__":
    collect_all_22nd_youtube()