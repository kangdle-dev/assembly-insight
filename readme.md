# Assembly Insight

국회의원 정보 분석 및 통합 관리 시스템

## 개요

- **목적**: 국회의원 프로필, 뉴스, YouTube 영상 데이터를 수집하고 분석
- **데이터**: 국회 공개API에서 의원 정보 수집 → MongoDB 저장 → 분석 및 내보내기
- **기술**: Python, MongoDB, NLP(Mecab)

## 주요 기능

- 국회의원 기본 정보 수집 및 DB 관리
- 의원 관련 뉴스 자동 수집 및 분석
- YouTube 영상 정보 통합
- NLP 기반 키워드 분석
- JSON 형식 데이터 내보내기 (프론트엔드용)

## 파일 구조

- `collect_members.py` - 의원 정보 수집
- `collect_news_22nd.py` - 뉴스 데이터 수집
- `collect_youtube_22nd.py` - YouTube 영상 수집
- `analysis_engine.py` - 뉴스 분석 및 키워드 추출
- `data_export/` - 분석 결과 JSON 저장 위치

## 필요 환경

- Python 3.x
- MongoDB
- 환경변수: `.env` 파일에 `GOV_API_KEY`, `MONGO_URI`, `DB_NAME` 설정
