import os
import json
import urllib.request
import time
import sys
import re
from pymongo import MongoClient, UpdateOne
from dotenv import load_dotenv
from datetime import datetime

# [1. 환경 및 설정 로드]
load_dotenv()
CLIENT_ID = os.getenv("NAVER_CLIENT_ID")
CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET")
MONGO_URI = os.getenv("MONGO_URI")
DB_NAME = os.getenv("DB_NAME")

client = MongoClient(MONGO_URI)
db = client[DB_NAME]
news_col = db['news']
members_col = db['members']

# [2. 검증된 메이저 언론사 필터링 맵]
# 이 목록에 포함된 도메인의 기사만 수집 대상이 됩니다.
TRUSTED_PRESS_MAP = {
    "yonhapnews.co.kr": "연합뉴스",
    "chosun.com": "조선일보",
    "hani.co.kr": "한겨레",
    "khan.co.kr": "경향신문",
    "donga.com": "동아일보",
    "joins.com": "중앙일보",
    "jtbc.co.kr": "JTBC",
    "sbs.co.kr": "SBS",
    "kbs.co.kr": "KBS",
    "mbc.co.kr": "MBC",
    "newsis.com": "뉴시스",
    "sedaily.com": "서울경제",
    "hankyung.com": "한국경제",
    "mk.co.kr": "매일경제",
    "segye.com": "세계일보",
    "kmib.co.kr": "국민일보",
    "munhwa.com": "문화일보",
    "ytn.co.kr": "YTN",
    "news1.kr": "뉴스1",
    "nocutnews.co.kr": "노컷뉴스",
    "heraldcorp.com": "헤럴드경제"
}

def get_trusted_press(original_link):
    """원문 링크를 분석하여 신뢰할 수 있는 언론사 명칭 반환 (필터링 핵심)"""
    if not original_link:
        return None
    for domain, name in TRUSTED_PRESS_MAP.items():
        if domain in original_link:
            return name
    return None

def print_progress(current, total, name, added=0, matched=0):
    """실시간 수집 상황 시각화"""
    percent = (current / total) * 100
    bar_len = 20
    filled_len = int(bar_len * current // total)
    bar = '█' * filled_len + '░' * (bar_len - filled_len)
    status = f"\r🚀 [{bar}] {percent:>5.1f}% | {current}/{total} | {name:<4} | +신규: {added:<2} | ~매칭: {matched:<2}"
    sys.stdout.write(status)
    sys.stdout.flush()

def collect_news_filtered():
    try:
        # 70라인 근처의 코드
        members = list(members_col.find({"is_22nd": True}, {"NAAS_NM": 1, "NAAS_CD": 1}))
        print(f"성공적으로 {len(members)}명의 데이터를 가져왔습니다.")
    except Exception as e:
        print(f"연결 에러 발생: {e}")
    # 22대 의원 명단 로드
    members = list(members_col.find({"is_22nd": True}, {"NAAS_NM": 1, "NAAS_CD": 1}))
    member_map = {m['NAAS_NM']: m['NAAS_CD'] for m in members}
    total = len(members)

    print(f"\n{'='*75}")
    print(f"🛡️  [국회 인사이트] 메이저 언론사 전용 뉴스 수집 엔진 가동")
    print(f"📡 필터링 기준: {len(TRUSTED_PRESS_MAP)}개 주요 언론사")
    print(f"📅 시작시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*75}\n")

    overall_new = 0
    overall_mod = 0

    for i, (name, target_cd) in enumerate(member_map.items(), 1):
        print_progress(i, total, name)

        # 네이버 API 쿼리 (의원명 검색)
        encText = urllib.parse.quote(f"국회의원 {name}")
        # display를 50으로 높여 필터링 후에도 충분한 기사가 남도록 조정
        url = f"https://openapi.naver.com/v1/search/news.json?query={encText}&display=50&sort=date"
        
        req = urllib.request.Request(url)
        req.add_header("X-Naver-Client-Id", CLIENT_ID)
        req.add_header("X-Naver-Client-Secret", CLIENT_SECRET)
        
        try:
            with urllib.request.urlopen(req) as response:
                items = json.loads(response.read().decode('utf-8')).get('items', [])
            
            ops = []
            for item in items:
                origin_link = item.get('originallink', item['link'])
                
                # 🚀 신뢰 언론사 필터링 수행
                press_name = get_trusted_press(origin_link)
                if not press_name:
                    continue # 리스트에 없는 매체는 패스
                
                link = item['link']
                title = item['title'].replace('<b>','').replace('</b>','').replace('&quot;','"')
                desc = item['description'].replace('<b>','').replace('</b>','').replace('&quot;','"')
                
                # 상호 참조 로직 (타 의원 언급 매핑)
                related = [target_cd]
                for m_name, m_cd in member_map.items():
                    if m_name in title or m_name in desc:
                        related.append(m_cd)
                
                # 네이버 날짜 문자열을 파이썬 datetime 객체로 변환
                dt_obj = datetime.strptime(item['pubDate'], "%a, %d %b %Y %H:%M:%S +0900")

                ops.append(UpdateOne(
                    {"link": link},
                    {
                        "$set": {
                            "title": title, 
                            "description": desc, 
                            "pubDate": dt_obj, 
                            "originallink": origin_link,
                            "press": press_name
                        },
                        "$addToSet": {"related_members": {"$each": list(set(related))}},
                        "$setOnInsert": {"created_at": datetime.now()}
                    },
                    upsert=True
                ))

            if ops:
                res = news_col.bulk_write(ops, ordered=False)
                overall_new += res.upserted_count
                overall_mod += res.modified_count
                print_progress(i, total, name, res.upserted_count, res.modified_count)

        except Exception as e:
            print(f"\n❌ {name} 수집 중 에러 발생: {str(e)[:50]}...")
            if "429" in str(e): break
            continue
        
        time.sleep(0.1)

    print(f"\n\n{'='*75}")
    print(f"🏁 신뢰 매체 뉴스 수집 완료 리포트")
    print(f"✨ 신규 수집: {overall_new:,} 건")
    print(f"🔄 중복 매칭: {overall_mod:,} 건")
    print(f"⏱️ 종료시간: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"{'='*75}\n")

if __name__ == "__main__":
    collect_news_filtered()