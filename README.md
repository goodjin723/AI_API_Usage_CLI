# **AI_API_Usage_CLI**

fal.ai API 사용량 추적 및 Notion 통합 CLI 도구

&nbsp;

## Features

- **사용량 조회**: fal.ai 모델별 API 사용량 조회
- **Notion 연동**: 사용량 데이터를 Notion 데이터베이스에 자동 저장
- **다양한 집계 단위**: 분/시간/일/주/월 단위 집계 지원
- **CLI 모드:** 명령줄 인자를 통한 자동화 지원

&nbsp;

## Requirements

- Python 3.9+ (tested on Python 3.12.12)
- pip

&nbsp;

## Installation

1. Clone the repository

```bash
git clone https://github.com/goodjin723/AI_API_Usage_CLI.git
cd AI_API_Usage_CLI
```

1. Install dependencies

```bash
pip install -r requirements.txt
```

&nbsp;

## Set up API-KEY

### 방법 1: 환경 변수 설정

**Windows (PowerShell):**

```powershell
$env:FAL_ADMIN_API_KEY="your-fal-api-key"
$env:NOTION_API_KEY="your-notion-api-key"  # Notion 사용 시
```

**Linux/Mac:**

```bash
export FAL_ADMIN_API_KEY="your-fal-api-key"
export NOTION_API_KEY="your-notion-api-key"  # Notion 사용 시
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
  "notion_api_key": "your-notion-api-key",
  "notion_databases": {
    "database_key_name": "your-notion-database-id"
  },
  "api_key": "your-fal-ai-admin-key"
}
```

### 방법 3: 인터랙티브 메뉴에서 설정

```bash
python main.py
# 메뉴에서 '3. API 키 설정' 선택
```

### 방법 4: CLI 인자 사용 (1회성)

```bash
python main.py -api-key <your-fal-ai-admin-key>
```

&nbsp;

## Notion Integration

### 1. Notion API 키 발급

1. [Notion Integrations](https://www.notion.so/my-integrations) 페이지 접속
2. "New integration" 클릭
3. Integration 이름 설정 후 생성
4. "Internal Integration Token" 복사

### 2. Notion 데이터베이스 준비

1. Notion에서 새 데이터베이스 생성
2. 데이터베이스에 Integration 연결 (우측 상단 ... → Connections)
3. 데이터베이스 URL에서 ID 복사
    - URL 형식: `https://www.notion.so/{workspace}/{database_id}?v=...`
    - `database_id` 부분을 복사
4. 데이터베이스 스키마 (이름 : 타입) &nbsp; **※ 이름(띄어쓰기 포함)과 타입 전부 동일해야 함.**
    - Date : Full date
    - Model : Title
    - Requests : Number
    - Quantity : Number
    - Cost ($) : Number
    - Unit Price ($) : Number
    - Time : Text
    - Model List : Select
    

### 3-1. 인터랙티브 메뉴에서 설정 (config.json 저장과 동일)

```bash
python main.py
# 메뉴에서 '4. Notion 설정' 선택
# '1. API 키 설정' → Notion API 키 입력
# '2. 데이터베이스 ID 추가/수정' → 키 별칭 및 데이터베이스 ID 입력
```

### 3-2. CLI에서 설정 (1회성)

```bash
python main.py -notion-api-key <your-notion-api-key> -notion-database-id <database_key_name>:<your-notion-database-id>
```

&nbsp;

## Usage

  ### 1. Interactive Mode (인터랙티브 모드)
  
  : 인자 없이 실행하면 대화형 메뉴가 표시
  
  ```bash
  python main.py
  ```
  
  **메뉴 옵션:**
  
  - `1. 모델 관리`: 추적할 모델 추가/삭제
  - `2. 날짜 범위 설정`: 조회 기간 설정
  - `3. API 키 설정`: fal.ai API 키 설정
  - `4. Notion 설정`: Notion 데이터베이스 연동 설정
  - `5. Notion 저장 옵션`: Notion 저장 모드(활성화/비활성화) 설정
  - `6. 조회 실행`: 설정된 조건으로 사용량 조회
  - `7. 종료`

### 2. CLI Mode (명령줄 모드)

: 명령줄 인자를 사용하여 자동화 및 스크립트 실행

**모델 지정법**

첫 실행 시 지정한 모델은 config.json 파일에 자동 저장. 재실행 시 생략 가능

**※ 단, cli 인자로 모델을 지정할 경우 config.json 파일 내 모델 리스트가 덮어 쓰여짐**

```bash
# 모델 지정 조회
python main.py -models "fal-ai/imagen4/preview/ultra"

# 여러 모델 동시 조회
python main.py -models "fal-ai/imagen4/preview/ultra,fal-ai/nano-banana"
```

**기간 설정법 (default : 7days)**

```bash
# 오늘 사용량 조회
python main.py -preset today

# 특정 기간 조회
python main.py -start-date 2025-01-01 -end-date 2025-01-31
```

**Notion 연동 사용 (default : Dry-run)**

```bash
# Notion에 저장
python main.py -notion

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

&nbsp;

## CLI Arguments Reference

| 인자 | 설명 | 예제 |
|------|------|------|
| `-api-key` | fal.ai Admin API 키 | `-api-key "your-key"` |
| `-models` | 추적할 모델 목록 (쉼표 구분) | `-models "model1,model2"` |
| `-preset` | 빠른 날짜 범위 선택 | `-preset last-7-days` |
| `-start-date` | 시작 날짜 (YYYY-MM-DD) | `-start-date 2025-01-01` |
| `-end-date` | 종료 날짜 (YYYY-MM-DD) | `-end-date 2025-01-31` |
| `-timeframe` | 집계 단위 (minute/hour/day/week/month) | `-timeframe hour` |
| `-timezone` | 타임존 | `-timezone "Asia/Seoul"` |
| `-bound-to-timeframe` | timeframe 경계 정렬 (true/false) | `-bound-to-timeframe true` |
| `-notion` | Notion 데이터베이스에 저장 | `-notion` |
| `-notion-api-key` | Notion API 키 | `-notion-api-key "your-key"` |
| `-notion-database-id` | Notion 데이터베이스 ID | `-notion-database-id "db-id"` |
| `-update-existing` | 중복 데이터 업데이트 모드 | `-update-existing` |
| `-dry-run` | 저장 없이 미리보기 | `-dry-run` |
| `-verbose` | 상세 로그 출력 | `-verbose` |

### Preset 옵션

- `today`: 오늘
- `yesterday`: 어제
- `last-7-days`: 지난 7일
- `last-30-days`: 지난 30일
- `this-month`: 이번 달

### Timeframe 미지정 시 자동 추론 규칙

- < 2시간 : minute
- < 2일 : hour
- < 64일 : day
- < 183일 : week
- ≥ 183일  : month

&nbsp;

## Project Structure

```
AI_API_Usage_CLI/
├── main.py              # 메인 실행 파일
├── api_client.py        # fal.ai API 클라이언트
├── config.py            # 설정 관리
├── date_utils.py        # 날짜 처리 유틸리티
├── formatter.py         # 출력 포맷팅
├── usage_tracker.py     # 사용량 데이터 처리
├── notion_integration.py # Notion 연동
├── notion_client.py     # Notion 클라이언트
├── cli_args.py          # CLI 인자 파싱
├── cli_menus.py         # 인터랙티브 메뉴
├── config.json          # 설정 파일
└── requirements.txt     # 의존성 목록
```
