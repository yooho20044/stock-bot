# 🚀 한국투자증권 자동 매매 시스템 프로젝트 요약 (2026-02-08)

본 프로젝트는 한국투자증권 API를 활용하여 맥북에서 개발하고 우분투 서버에 도커로 배포한 자동 주식 매매 시스템입니다.

## 🛠 기술 스택
- **Language**: Python 3.12
- **API**: 한국투자증권 KIS Open API (python-kis 라이브러리 커스텀 활용)
- **Library**: Pandas (데이터 분석), schedule (작업 예약), requests, python-dotenv
- **Notification**: Slack (Incoming Webhooks)
- **Deployment**: Docker, Docker Hub, Ubuntu 24.04

## 📂 파일 구조
- `main.py`: 프로그램 진입점. 스케줄러 관리, 장 개장 확인, 요약 리포트 로직 포함.
- `trading_algo.py`: 핵심 알고리즘. 이동평균선(SMA 5/20) + RSI(14) 필터 기반 매매 및 주문 실행.
- `notifier.py`: 슬랙 알림 전송 모듈.
- `.env`: API 키, 계좌번호, 슬랙 Webhook URL 등 민감 정보 관리.
- `Dockerfile`: 서버 배포를 위한 도커 설정 파일.
- `requirements.txt`: 의존성 라이브러리 목록.

## ✨ 주요 기능
1. **자동 매매 전략**:
   - 1분 간격으로 시장 데이터 분석.
   - **매수**: SMA 5가 SMA 20을 상향 돌파하고 RSI가 70 미만일 때.
   - **매도**: SMA 5가 SMA 20을 하향 돌파하고 RSI가 30 초과일 때.
2. **운영 최적화**:
   - **장 개장 확인**: 평일 09:00 ~ 15:30에만 API 요청 (불필요한 트래픽 및 오류 방지).
   - **시간별 요약**: 매분 발생하는 알림 대신, 1시간 동안의 거래 내역을 모아 슬랙으로 전송.
   - **토큰 캐싱**: `keep_token=True`를 통해 API 접근 토큰 재사용 및 발급 제한 우회.
3. **자금 관리 및 포지션 사이징 (신규)**:
   - **동적 수량 계산**: 고정 1주 매매에서 탈피하여 계좌 잔고 및 변동성 기반 수량 산출.
   - **전략 옵션**: 고정 비율(Fixed Fractional), 변동성 조절(ATR 기반), 수학적 최적화(Half-Kelly) 지원.
   - **분할 진입**: RSI 강도에 따라 진입 비중을 조절(20%~100%)하여 리스크 분산.
4. **안정성**:
   - 도커 컨테이너 기반 24시간 무중단 가동.
   - 치명적 오류 발생 시 슬랙 알림 후 자동 종료 및 서버 레벨 재시작 설정.

## 🚀 배포 및 실행 (Ubuntu)
1. **이미지 업데이트 (Mac)**:
   `docker buildx build --platform linux/amd64 -t [ID]/stock-bot:latest --push .`
2. **서버 실행 (Ubuntu)**:
   `docker run -d --name stock-bot-run --restart always [ID]/stock-bot:latest`
