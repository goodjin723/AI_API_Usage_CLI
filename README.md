# **AI_API_Usage_CLI**

AI API 사용량 추적 및 Invoice 수집 자동화 CLI 도구

&nbsp;

## Features

- **fal.ai 사용량 추적**: 모델별 API 사용량 조회 및 분석
- **Invoice 자동 수집**: Gmail에서 AI 서비스 Invoice 자동 추출
- **Notion 자동 연동**: 사용량 및 Invoice 데이터를 Notion DB에 자동 저장
- **다양한 집계 단위**: 분/시간/일/주/월 단위 집계 지원
- **인터랙티브 메뉴**: 직관적인 계층형 메뉴 시스템
- **CLI 모드**: 명령줄 인자를 통한 자동화 지원

&nbsp;

## Requirements

- Python 3.9+ (tested on Python 3.12.12)
- pip
- Gmail API 접근 권한 (Invoice 수집 시)

&nbsp;

## Installation

1. Clone the repository

```bash
git clone https://github.com/goodjin723/AI_API_Usage_CLI.git
cd AI_API_Usage_CLI
```

2. Install dependencies

```bash
pip install -r requirements.txt
```

&nbsp;

## Set up API Keys

### 방법 1: 환경 변수 설정

**Windows (PowerShell):**

```powershell
$env:FAL_ADMIN_API_KEY="your-fal-api-key"
$env:OPENAI_API_KEY="your-openai-api-key"      # Invoice 추출용
$env:NOTION_API_KEY="your-notion-api-key"      # Notion 사용 시
```

**Linux/Mac:**

```bash
export FAL_ADMIN_API_KEY="your-fal-api-key"
export OPENAI_API_KEY="your-openai-api-key"    # Invoice 추출용
export NOTION_API_KEY="your-notion-api-key"    # Notion 사용 시
```

### 방법 2: config.json 파일 설정

프로젝트 루트에 `config.json` 파일을 생성:

```json
{
  "timezone": "Asia/Seoul",
  "default_date_range": {
    "preset": "last-7-days"
  },
  "models": [
    "fal-ai/your-model-id"
  ],
  "fal_ai_api_key": "your-fal-ai-admin-key",
  "openai_api_key": "your-openai-api-key",
  "notion_api_key": "your-notion-api-key",
  "notion_databases": {
    "fal_ai": "your-fal-ai-notion-database-id",
    "invoice": "your-invoice-notion-database-id"
  },
  "invoice_keywords": [
    "Your Replit receipt",
    "Your receipt from Gamma",
    "AWS Invoice"
  ]
}
```

### 방법 3: 인터랙티브 메뉴에서 설정

```bash
python main.py
# 메뉴에서 '1. 공통 설정' > '1. API 키 설정' 선택
```

### 방법 4: CLI 인자 사용 (1회성)

```bash
python main.py -fal-ai-api-key <your-fal-ai-admin-key>
```

&nbsp;

## Gmail API 설정

Invoice 수집 기능은 Gmail MCP를 통해 수집됨.

### 1. Google Cloud Console 설정

1. [Google Cloud Console](https://console.cloud.google.com/) 접속
2. 새 프로젝트 생성 또는 기존 프로젝트 선택
3. "API 및 서비스" > "라이브러리" 이동
4. "Gmail API" 검색 및 활성화

### 2. OAuth 2.0 인증 정보 생성

1. "API 및 서비스" > "사용자 인증 정보" 이동
2. "사용자 인증 정보 만들기" > "OAuth 클라이언트 ID" 선택
3. 애플리케이션 유형: "웹 애플리케이션" 선택
4. 승인된 리디렉션 URL에 `http://localhost:8888/` 추가
5. 생성된 JSON 파일 다운로드
6. 파일 이름을 `credentials.json`으로 변경
7. 프로젝트 루트 디렉토리에 저장

### 3. 접근 계정 설정

1. "API 및 서비스" > "대상" 이동
2. "테스트 사용자" > "Add users" 선택
3. Gmail 수집 계정 추가

### 4. 데이터 액세스 설정

1. "API 및 서비스" > "데이터 액세스" 이동
2. "범위 추가 또는 삭제" > 직접 범위에 `https://www.googleapis.com/auth/gmail.readonly` 입력
3. "테이블 추가" > "업데이트" > "Save" 선택

### 5. 첫 실행 시 인증

invoice 첫 실행 시 브라우저가 열리면서 Google 로그인 및 권한 승인 요청이 표시됩니다.
승인 후 `google_token.json` 파일이 자동 생성되며, 이후 실행 시에는 자동 인증됩니다.

&nbsp;

## Notion Integration

### 1. Notion API 키 발급

1. [Notion Integrations](https://www.notion.so/my-integrations) 페이지 접속
2. "New integration" 클릭
3. Integration 이름 설정 후 생성
4. "Internal Integration Token" 복사

### 2. Notion 데이터베이스 준비

이 도구는 **2개의 Notion 데이터베이스**를 사용합니다:
- `fal_ai`: fal.ai 사용량 추적용
- `invoice`: Invoice 데이터 저장용

> 💡 **빠른 시작**: [🌱Notion DB Template](https://four-zircon-001.notion.site/AI_API_Usage_CLI-Notion-DB-Template-2afc5a12fc7b80be8bd2d71257df6ab9?source=copy_link_)을 복제하여 사용할 수 있습니다.

#### fal.ai 사용량 추적 데이터베이스

1. Notion에서 새 데이터베이스 생성
2. 데이터베이스에 Integration 연결 (우측 상단 ... → Connections)
3. 데이터베이스 URL에서 ID 복사
    - URL 형식: `https://www.notion.so/{workspace}/{database_id}?v=...`
    - `database_id` 부분을 복사
4. 아래 속성 생성 **※ 속성 이름(띄어쓰기 포함)과 타입이 정확히 일치해야 함**

| 속성 이름 | 타입 |
|-----------|------|
| Date | Full date |
| Model | Title |
| Requests | Number |
| Quantity | Number |
| Cost ($) | Number |
| Unit Price ($) | Number |
| Time | Text |
| Model List | Select |
| Key Name | Select |


#### Invoice 데이터베이스

1. 새로운 Notion 데이터베이스 생성
2. Integration 연결
3. 아래 속성 생성

| 속성 이름 | 타입 |
|-----------|------|
| Invoice Number | Title |
| Date Paid | Date |
| Service | Select |
| Amount ($) | Number |
| Email Subject | Text |
| Description | Text |
| Period | Text |
| Paid Status | Status |

### 3. 데이터베이스 ID 설정

#### 인터랙티브 메뉴에서 설정

```bash
python main.py
# '1. 공통 설정' > '2. Notion DB 설정' 선택
# fal_ai: fal.ai 사용량 DB ID 입력
# invoice: Invoice DB ID 입력
```

#### config.json에 직접 입력

```json
{
  "notion_databases": {
    "fal_ai": "your-fal-ai-database-id",
    "invoice": "your-invoice-database-id"
  }
}
```

&nbsp;

## Usage

### 1. Interactive Mode (인터랙티브 모드)

인자 없이 실행하면 계층형 메뉴가 표시됩니다.

```bash
python main.py
```

#### 메인 메뉴 구조

```
>> AI API 사용량 추적 CLI <<

1. 공통 설정
   ├─ 1. API 키 설정 (fal ai, OpenAI, Notion)
   └─ 2. Notion DB 설정 (fal_ai, invoice)

2. fal ai 사용량 추적
   ├─ 1. 모델 관리 (추가/삭제)
   ├─ 2. 날짜 범위 설정
   └─ 3. 조회 실행
       └─ Notion 저장 여부 선택 (prompt)

3. Invoices 수집
   ├─ 1. 키워드 설정 (검색할 서비스명)
   ├─ 2. 기간 설정
   └─ 3. 조회 실행
       └─ Notion 저장 여부 선택 (prompt)

0. 종료
```

#### 각 메뉴 기능 설명

**공통 설정**
- API 키 설정: fal.ai, OpenAI, Notion API 키 관리
- Notion DB 설정: fal_ai, invoice 데이터베이스 ID 설정

**fal ai 사용량 추적**
- 모델 관리: 추적할 fal.ai 모델 추가/삭제
- 날짜 범위 설정: 프리셋 또는 커스텀 날짜 범위 설정
- 조회 실행: 설정된 조건으로 사용량 조회 및 Notion 저장 선택

**Invoices 수집**
- 키워드 설정: Gmail에서 검색할 서비스 키워드 관리
- 기간 설정: Invoice 검색 기간 설정
- 조회 실행: Gmail에서 Invoice 추출 및 Notion 저장 선택

&nbsp;

### 2. CLI Mode (명령줄 모드)

명령줄 인자를 사용하여 자동화 및 스크립트 실행

#### fal.ai 사용량 추적

**기본 사용법**

```bash
# 모델 지정 조회 (첫 실행 시 config.json에 저장됨)
python main.py -models "fal-ai/imagen4/preview/ultra"

# 여러 모델 동시 조회
python main.py -models "fal-ai/imagen4/preview/ultra,fal-ai/nano-banana"

# config.json에 저장된 모델로 조회 (모델 재지정 불필요)
python main.py -preset today
```

**기간 설정 (default: last-7-days)**

```bash
# 프리셋 사용
python main.py -preset today
python main.py -preset yesterday
python main.py -preset last-30-days

# 특정 기간 조회
python main.py -start-date 2025-01-01 -end-date 2025-01-31
```

**Notion 연동**

```bash
# Notion에 저장
python main.py -models "fal-ai/your-model" -notion

# 중복 데이터 업데이트 모드
python main.py -notion -update-existing

# Dry-run (실제 저장 없이 미리보기)
python main.py -dry-run
```

**고급 옵션**

```bash
# 시간 단위 집계 + 상세 로그
python main.py -preset today -timeframe hour -verbose

# 타임존 지정
python main.py -preset today -timezone "UTC"

# 월 단위 집계
python main.py -preset this-month -timeframe month
```

#### Invoice 수집

**기본 사용법**

```bash
# Invoice 수집 모드 (최근 90일)
python main.py -invoice

# Notion에 저장
python main.py -invoice -notion

# 중복 Invoice 업데이트
python main.py -invoice -notion -update-existing
```

**검색 키워드 지정**

```bash
# 특정 서비스 키워드로 검색
python main.py -invoice -invoice-keywords "stripe,aws,openai"

# config.json에 저장된 키워드 사용 (키워드 재지정 불필요)
python main.py -invoice
```

**기간 설정**

```bash
# 최근 N일
python main.py -invoice -invoice-days 30

# 특정 기간
python main.py -invoice -invoice-start-date 2025-01-01 -invoice-end-date 2025-01-31
```

**완전한 예제**

```bash
# 특정 키워드로 검색하고 Notion에 저장
python main.py -invoice \
  -invoice-keywords "stripe,anthropic,openai" \
  -invoice-start-date 2025-01-01 \
  -invoice-end-date 2025-01-31 \
  -notion \
  -update-existing \
  -verbose
```

&nbsp;

## CLI Arguments Reference

### 공통 인자

| 인자 | 설명 | 예제 |
|------|------|------|
| `-verbose` | 상세 로그 출력 | `-verbose` |
| `-notion` | Notion 데이터베이스에 저장 | `-notion` |
| `-notion-api-key` | Notion API 키 | `-notion-api-key "your-key"` |
| `-update-existing` | 중복 데이터 업데이트 모드 | `-update-existing` |
| `-dry-run` | 저장 없이 미리보기 | `-dry-run` |

### fal.ai 사용량 추적 인자

| 인자 | 설명 | 예제 |
|------|------|------|
| `-fal-ai-api-key` | fal.ai Admin API 키 | `-fal-ai-api-key "your-key"` |
| `-models` | 추적할 모델 목록 (쉼표 구분) | `-models "model1,model2"` |
| `-preset` | 빠른 날짜 범위 선택 | `-preset last-7-days` |
| `-start-date` | 시작 날짜 (YYYY-MM-DD) | `-start-date 2025-01-01` |
| `-end-date` | 종료 날짜 (YYYY-MM-DD) | `-end-date 2025-01-31` |
| `-timeframe` | 집계 단위 (minute/hour/day/week/month) | `-timeframe hour` |
| `-timezone` | 타임존 | `-timezone "Asia/Seoul"` |
| `-bound-to-timeframe` | timeframe 경계 정렬 (true/false) | `-bound-to-timeframe true` |
| `-notion-database-id` | Notion 데이터베이스 ID | `-notion-database-id "db-id"` |

### Invoice 수집 인자

| 인자 | 설명 | 기본값 | 예제 |
|------|------|--------|------|
| `-invoice` | Invoice 수집 모드 활성화 | - | `-invoice` |
| `-invoice-keywords` | 검색 키워드 (쉼표 구분) | config.json | `-invoice-keywords "stripe,aws"` |
| `-invoice-start-date` | 검색 시작 날짜 (YYYY-MM-DD) | - | `-invoice-start-date 2025-01-01` |
| `-invoice-end-date` | 검색 종료 날짜 (YYYY-MM-DD) | - | `-invoice-end-date 2025-01-31` |
| `-invoice-days` | 최근 N일 검색 | 90 | `-invoice-days 30` |
| `-open-ai-api-key` | OpenAI API 키 (Gmail MCP용) | config.json | `-open-ai-api-key "your-key"` |

### Preset 옵션

- `today`: 오늘
- `yesterday`: 어제
- `last-7-days`: 지난 7일
- `last-30-days`: 지난 30일
- `this-month`: 이번 달

### Timeframe 기본값

CLI에서 `-timeframe`을 지정하지 않으면 `day`가 기본값으로 사용됩니다.

&nbsp;

## Project Structure

```
AI_API_Usage_CLI/
├── main.py                  # 메인 실행 파일
├── api_client.py            # fal.ai API 클라이언트
├── config.py                # 설정 관리
├── date_utils.py            # 날짜 처리 유틸리티
├── formatter.py             # 출력 포맷팅 (사용량 & Invoice)
├── usage_tracker.py         # 사용량 데이터 처리
├── notion_integration.py    # Notion 연동 (사용량 & Invoice)
├── cli_args.py              # CLI 인자 파싱
├── cli_menus.py             # 인터랙티브 메뉴
├── invoice_gmail_client.py  # Gmail API 클라이언트 (Invoice 추출)
├── invoice_openai_parser.py # OpenAI API를 통한 Invoice 파싱
├── google_auth.py           # Google OAuth2 인증
├── config.json              # 설정 파일
├── credentials.json         # Google OAuth 인증 정보 (사용자 생성)
├── token.json               # Google OAuth 토큰 (자동 생성)
└── requirements.txt         # 의존성 목록
```

&nbsp;

## Troubleshooting

### Invoice 수집 시 "credentials.json not found" 에러

Gmail API 인증 정보 파일이 없는 경우입니다.
[Gmail API 설정](#gmail-api-설정) 섹션을 참고하여 `credentials.json` 파일을 생성하세요.

### Notion 저장 시 "Database not found" 에러

1. Notion 데이터베이스에 Integration이 연결되어 있는지 확인
2. config.json의 `notion_databases` 설정이 올바른지 확인
3. 데이터베이스 속성(컬럼)이 정확히 일치하는지 확인

### "API 키가 설정되지 않았습니다" 에러

1. 환경 변수 또는 config.json에 API 키가 설정되어 있는지 확인
2. 인터랙티브 메뉴에서 '공통 설정' > 'API 키 설정' 선택하여 설정

&nbsp;

## Contact

- GitHub: [@goodjin723](https://github.com/goodjin723)
- Repository: [AI_API_Usage_CLI](https://github.com/goodjin723/AI_API_Usage_CLI)
