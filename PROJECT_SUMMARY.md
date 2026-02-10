# 🚀 한국투자증권 자동 매매 시스템 프로젝트 요약 (최종 업데이트: 2026-02-10)

본 프로젝트는 한국투자증권 API를 활용하여 맥북에서 개발하고 우분투 서버에 도커로 배포한 자동 주식 매매 시스템입니다.

## 🛠 최근 작업 내역 (2026-02-10)
- **잔액 조회 기능 정상화 및 안정화**: 
  - `inquire-psbl-order` (VTTC8435R) TR ID를 사용하여 정확한 '미수 없는 매수 가능 현금'을 조회하도록 수정.
  - API 응답이 단일 객체(`output`) 또는 리스트(`output2`) 형태로 오는 모든 경우를 대응하도록 방어적 코드 작성.
  - `KisDynamicDict` 객체 접근 방식(getattr 사용)을 최적화하여 런타임 오류 방지.
- **모의투자 환경 최적화**: 잔액 조회 시 모의투자용 TR ID(`VTTC8435R`, `VTTC8434R`)를 적용하여 데이터 연동 오류 해결.
- **응답 처리 개선**: API 응답 데이터에서 출력 필드를 안전하게 추출하도록 로직 보완.

## 🛠 기술 스택
- **Language**: Python 3.12
- **API**: 한국투자증권 KIS Open API (python-kis 라이브러리 커스텀 활용)
- **Library**: Pandas (데이터 분석), schedule (작업 예약), requests, python-dotenv
- **Notification**: Slack (Incoming Webhooks)
- **Deployment**: Docker, GitHub Actions (CI/CD), Watchtower (Auto Update), Ubuntu 24.04

## 📂 파일 구조
- `main.py`: 프로그램 진입점. 스케줄러 관리, 잔고 조회, 포지션 사이징 로직 포함.
- `trading_algo.py`: 핵심 알고리즘. SMA + RSI 신호, ATR 기반 변동성 조절 및 켈리 공식 적용.
- `notifier.py`: 슬랙 알림 전송 모듈.
- `.github/workflows/docker-build.yml`: GitHub Actions 자동 빌드 및 푸시 설정.
- `.env`: API 키, 계좌번호, 전략 선택 등 민감 정보 관리.
- `Dockerfile`: 서버 배포 설정.

## ✨ 주요 기능
1. **자동 매매 전략**:
   - 1분 간격 시장 데이터 분석 및 SMA(5/20) 골든/데드크로스 신호 생성.
   - RSI(14) 필터를 통한 과매수/과매도 구간 진입 방지.
2. **자금 관리 및 포지션 사이징**:
   - **동적 수량 계산**: 계좌 잔고를 실시간 조회하여 투자 비중 결정.
   - **전략 옵션**: 고정 비율(Fixed), 변동성 조절(ATR), 수학적 최적화(Half-Kelly).
   - **분할 진입**: RSI 강도에 따라 20%~100% 사이로 매수 비중 차등 할당.
3. **운영 자동화 (CI/CD)**:
   - **GitHub Actions**: 코드 Push 시 Docker Hub로 자동 빌드/푸시.
   - **Watchtower**: 서버에서 새 이미지를 감지하여 무중단 자동 재시작.
4. **안정성**:
   - 도커 기반 무중단 가동 및 에러 발생 시 슬랙 즉시 알림.

## 🚀 배포 및 자동화 흐름
1. **코드 수정 (Local)**: 맥북 또는 윈도우에서 코드 수정 후 `git push`.
2. **자동 빌드 (GitHub)**: GitHub Actions가 `linux/amd64` 이미지 빌드 후 Docker Hub 전송.
3. **자동 업데이트 (Server)**: 우분투의 Watchtower가 1분 이내에 새 이미지를 감지하여 컨테이너 갱신.
