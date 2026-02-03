import os
import time
import logging
from datetime import datetime
from pymongo import MongoClient
from openai import OpenAI
from dotenv import load_dotenv

# 1. 설정 및 환경 로드
load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
mongo_client = MongoClient(os.getenv("MONGO_URI"))
db = mongo_client['assembly_insight']
collection = db['members_policy']

# 2. 로그 설정 (파일 저장용)
log_filename = f"analysis_log_{datetime.now().strftime('%Y%m%d')}.txt"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler()
    ]
)

def generate_ai_summary(member, current_idx, total_count):
    member_name = member.get('name')
    current_bill_count = len(member.get('representative_bills', []))
    prev_bill_count = member.get('prev_bill_count', 0)
    
    # [로직] 법안 수에 변화가 없다면 건너뜀
    if current_bill_count == prev_bill_count and member.get('ai_summary'):
        logging.info(f"[{current_idx}/{total_count}] ⏭️ {member_name}: 변동 사항 없음 (건너뜀)")
        return "skipped"

    logging.info(f"[{current_idx}/{total_count}] 🚀 {member_name}: 분석 시작 (법안 수: {prev_bill_count} -> {current_bill_count})")

    # 분석용 법안 제목 추출
    bills = member.get('representative_bills', [])
    bill_titles = [b.get('BILL_NAME') or b.get('bill_name') for b in bills[:30] if b.get('BILL_NAME') or b.get('bill_name')]
    titles_str = ", ".join(bill_titles)

    if not titles_str:
        summary = "제22대 국회 임기 초반으로, 현재 분석 가능한 대표 발의 데이터가 부족합니다."
    else:
        prompt = f"""
        당신은 대한민국 국회 의정 활동을 정밀 분석하는 '국회 인사이트 프로젝트'의 수석 분석관입니다.
        다음은 {member_name} 의원이 제22대 국회에서 대표 발의한 법안 리스트입니다.

        [법안 리스트]
        {titles_str}

        위 데이터를 바탕으로 다음 지침에 따라 {member_name} 의원의 정책 성향을 분석하세요:

        1. [전문 분야]: 법안 제목들에서 공통적으로 발견되는 핵심 산업이나 사회적 테마를 식별하세요.
        2. [입법 페르소나]: 단순 나열이 아닌 '보호자', '개혁가', '조정자', '혁신가' 등 의원의 입법 성격을 규정하세요.
        3. [사회적 가치]: 이 의원의 입법이 유권자의 삶(경제, 복지, 안전 등)에 미치는 실질적인 효과를 도출하세요.

        작성 규칙:
        - 반드시 아래의 '출력 형식'을 엄격히 준수할 것.
        - 전문 용어와 부드러운 문체를 섞어 신뢰감 있는 보고서 톤으로 작성할 것.
        - 2~3문장 이내로 명확하게 작성할 것.

        출력 형식:
        "{member_name} 의원은 주로 [핵심 정책 분야]에 집중하며, [입법 성격(예: 현장 밀착형, 미래 지향적 등)] 입법 활동을 통해 [수혜 대상 또는 사회적 가치]를 개선하는 데 주력하고 있습니다. 특히 [대표 키워드 또는 구체적 사례] 관련 법안들을 통해 국민의 실생활과 직결된 [기대 효과]를 만들어내는 행보를 보입니다."
        """
        try:
            response = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                temperature=0.5
            )
            summary = response.choices[0].message.content.strip()
        except Exception as e:
            logging.error(f"❌ {member_name} AI 오류: {e}")
            return "error"

    # DB 업데이트 (ai_summary 갱신 및 현재 법안 수를 prev_bill_count로 저장)
    collection.update_one(
        {"name": member_name},
        {
            "$set": {
                "ai_summary": summary,
                "prev_bill_count": current_bill_count,
                "last_ai_update": datetime.now()
            }
        }
    )
    logging.info(f"   💾 {member_name}: 분석 완료 및 DB 저장")
    return "success"

def main():
    members = list(collection.find({}))
    total = len(members)
    results = {"success": 0, "skipped": 0, "error": 0}

    logging.info("="*50)
    logging.info(f"분석 시작: 총 {total}명 대상")
    logging.info("="*50)

    for idx, m in enumerate(members, 1):
        status = generate_ai_summary(m, idx, total)
        results[status] += 1
        
    # 최종 리포트 출력 및 로그 저장
    logging.info("="*50)
    logging.info(f"최종 결과 - 성공: {results['success']}, 건너뜀: {results['skipped']}, 에러: {results['error']}")
    logging.info(f"로그 파일이 저장되었습니다: {log_filename}")
    logging.info("="*50)

if __name__ == "__main__":
    main()