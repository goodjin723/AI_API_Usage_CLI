"""
Gmail Invoice 추출 클라이언트
OpenAI Response API + Gmail MCP를 사용하여 이메일에서 invoice 정보 추출
"""
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import config
import google_auth


def fetch_invoices(
    search_keywords: Optional[str] = None,
    model: str = "gpt-4o-mini",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 90,
    verbose: bool = False
) -> List[Dict[str, Any]]:
    """
    Gmail에서 invoice 메일을 검색하고 구조화된 데이터로 추출
    
    Args:
        search_keywords: Gmail 검색 키워드 (None이면 config에서 가져옴)
        model: OpenAI 모델 (gpt-4o 또는 gpt-4o-mini)
        start_date: 검색 시작 날짜 (YYYY-MM-DD, None이면 days 사용)
        end_date: 검색 종료 날짜 (YYYY-MM-DD, None이면 오늘)
        days: start_date가 None일 때 최근 N일 검색 (기본: 90일)
        verbose: 상세 로그 출력
    
    Returns:
        List[Dict]: Invoice 데이터 리스트
        [
            {
                "invoice_id": "INV-2024-001",
                "date": "2024-01-15",
                "amount": 29.99,
                "description": "Replit Cycles - January 2024",
                "period": "2024-01-01 ~ 2024-01-31",
                "service": "Replit",
                "email_subject": "Your Replit receipt for January 2024"
            },
            ...
        ]
    
    Raises:
        ImportError: openai 패키지가 설치되지 않은 경우
        Exception: API 호출 실패 시
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "❌ openai 패키지가 필요합니다.\n"
            "설치: pip install openai"
        )
    
    # 검색 키워드 가져오기
    if search_keywords is None:
        search_keywords = config.get_invoice_search_keywords()
    
    # 날짜 범위 계산
    if end_date is None:
        end_date_obj = datetime.now()
        end_date = end_date_obj.strftime("%Y-%m-%d")
    else:
        end_date_obj = datetime.strptime(end_date, "%Y-%m-%d")
    
    if start_date is None:
        start_date_obj = end_date_obj - timedelta(days=days)
        start_date = start_date_obj.strftime("%Y-%m-%d")
    else:
        start_date_obj = datetime.strptime(start_date, "%Y-%m-%d")
    
    if verbose:
        print(f"[DEBUG] 검색 키워드: {search_keywords}")
        print(f"[DEBUG] 사용 모델: {model}")
        print(f"[DEBUG] 검색 기간: {start_date} ~ {end_date}")
    
    # Google Access Token 가져오기
    if verbose:
        print("\n[단계 1] Google OAuth 토큰 로드 중...")
    
    try:
        access_token = google_auth.load_access_token()
    except Exception as e:
        raise Exception(f"Google 인증 실패: {e}")
    
    if verbose:
        print("✓ Google 인증 완료")
    
    # OpenAI API 키 가져오기
    openai_api_key = config.get_openai_api_key()
    if not openai_api_key:
        raise ValueError(
            "OpenAI API 키가 필요합니다.\n"
            "환경 변수 OPENAI_API_KEY를 설정하거나 config.json에 추가하세요."
        )
    
    # OpenAI 클라이언트 생성
    client = OpenAI(api_key=openai_api_key)
    
    # 프롬프트 생성
    prompt = _create_extraction_prompt(search_keywords, start_date, end_date)
    
    if verbose:
        print(f"\n[단계 2] Gmail 메일 검색 및 분석 중...")
        print(f"[DEBUG] 프롬프트 길이: {len(prompt)} 문자")
    
    # Response API 호출
    try:
        response = client.responses.create(
            model=model,
            tools=[
                {
                    "type": "mcp",
                    "server_label": "google_gmail",
                    "connector_id": "connector_gmail",
                    "authorization": access_token,
                    "require_approval": "never",
                }
            ],
            input=prompt
        )
    except Exception as e:
        raise Exception(f"OpenAI Response API 호출 실패: {e}")
    
    if verbose:
        print("✓ API 호출 완료")
        print(f"\n[단계 3] 응답 데이터 파싱 중...")
    
    # 응답 파싱
    output_text = response.output_text
    
    if verbose:
        print(f"[DEBUG] 응답 길이: {len(output_text)} 문자")
        print(f"[DEBUG] 응답 미리보기: {output_text[:200]}...")
    
    # JSON 파싱
    try:
        # GPT가 마크다운 코드 블록으로 감쌀 수 있으므로 제거
        cleaned_text = output_text.strip()
        if cleaned_text.startswith("```json"):
            cleaned_text = cleaned_text[7:]
        if cleaned_text.startswith("```"):
            cleaned_text = cleaned_text[3:]
        if cleaned_text.endswith("```"):
            cleaned_text = cleaned_text[:-3]
        
        cleaned_text = cleaned_text.strip()
        
        invoices = json.loads(cleaned_text)
        
        if not isinstance(invoices, list):
            raise ValueError("응답이 리스트 형식이 아닙니다.")
        
    except json.JSONDecodeError as e:
        if verbose:
            print(f"[ERROR] JSON 파싱 실패: {e}")
            print(f"[DEBUG] 원본 응답:\n{output_text}")
        raise Exception(f"응답 JSON 파싱 실패: {e}")
    
    if verbose:
        print(f"✓ 파싱 완료: {len(invoices)}개 invoice 발견")
    
    # 데이터 검증 및 정제
    validated_invoices = []
    for idx, invoice in enumerate(invoices):
        try:
            validated = _validate_invoice(invoice, verbose)
            validated_invoices.append(validated)
        except Exception as e:
            if verbose:
                print(f"[WARNING] Invoice {idx+1} 검증 실패: {e}")
            continue
    
    if verbose:
        print(f"\n[완료] 총 {len(validated_invoices)}개의 유효한 invoice 추출")
    
    return validated_invoices


def _create_extraction_prompt(search_keywords: str, start_date: str, end_date: str) -> str:
    """Invoice 추출 프롬프트 생성"""
    # Gmail 날짜 형식으로 변환 (YYYY/MM/DD)
    gmail_start = start_date.replace("-", "/")
    gmail_end = end_date.replace("-", "/")
    
    return f"""
Search Gmail for emails matching: "{search_keywords}"

Date range: after:{gmail_start} before:{gmail_end}

For each invoice email found, extract the following information and return as a JSON array:

[
  {{
    "invoice_id": "string (invoice/receipt number, e.g., 'INV-2024-001')",
    "date": "YYYY-MM-DD (invoice date)",
    "amount": number (total amount in USD, numeric only without $ symbol)",
    "description": "string (brief description of charges/services)",
    "period": "string (billing period if mentioned, e.g., 'Jan 1-31, 2024' or 'N/A')",
    "service": "string (service/company name, e.g., 'Replit', 'AWS', etc.)",
    "email_subject": "string (original email subject line)"
  }}
]

Important extraction rules:
1. Return ONLY valid JSON array, no markdown code blocks
2. If no invoice emails found, return empty array: []
3. "amount" must be a number (not string), extract numeric value only
4. "date" must be in YYYY-MM-DD format
5. If invoice_id is not explicitly stated, use a generated ID like "INV-YYYY-MM-DD-XXX"
6. "period" should capture billing period if mentioned in email, otherwise use "N/A"
7. "service" should identify the service provider from email sender or content
8. Extract data accurately from email body, subject, and metadata
9. Focus on invoice/receipt/billing emails only, ignore other types

Return the JSON array now.
""".strip()


def _validate_invoice(invoice: Dict[str, Any], verbose: bool = False) -> Dict[str, Any]:
    """
    Invoice 데이터 검증 및 정제
    
    Args:
        invoice: 원본 invoice 데이터
        verbose: 디버그 로그 출력
    
    Returns:
        Dict: 검증되고 정제된 invoice 데이터
    
    Raises:
        ValueError: 필수 필드 누락 또는 형식 오류
    """
    # 필수 필드 확인
    required_fields = ["invoice_id", "date", "amount", "service"]
    for field in required_fields:
        if field not in invoice:
            raise ValueError(f"필수 필드 누락: {field}")
    
    # 날짜 형식 검증
    try:
        datetime.strptime(invoice["date"], "%Y-%m-%d")
    except ValueError:
        raise ValueError(f"잘못된 날짜 형식: {invoice['date']} (YYYY-MM-DD 필요)")
    
    # 금액 검증
    try:
        amount = float(invoice["amount"])
        if amount < 0:
            raise ValueError(f"음수 금액: {amount}")
    except (ValueError, TypeError):
        raise ValueError(f"잘못된 금액 형식: {invoice['amount']}")
    
    # 정제된 데이터 반환
    return {
        "invoice_id": str(invoice["invoice_id"]).strip(),
        "date": invoice["date"],
        "amount": float(invoice["amount"]),
        "description": str(invoice.get("description", "N/A")).strip(),
        "period": str(invoice.get("period", "N/A")).strip(),
        "service": str(invoice["service"]).strip(),
        "email_subject": str(invoice.get("email_subject", "N/A")).strip()
    }


def format_for_notion(invoices: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Invoice 데이터를 Notion 형식으로 변환
    
    Args:
        invoices: Invoice 데이터 리스트
    
    Returns:
        List[Dict]: Notion 형식의 데이터 리스트
    """
    notion_records = []
    
    for invoice in invoices:
        record = {
            "invoice_id": invoice["invoice_id"],
            "date": invoice["date"],
            "amount": invoice["amount"],
            "description": invoice["description"],
            "period": invoice["period"],
            "service": invoice["service"],
            "email_subject": invoice["email_subject"]
        }
        notion_records.append(record)
    
    return notion_records


if __name__ == "__main__":
    """
    직접 실행 시 테스트 모드
    
    사용법:
        python invoice_gmail_client.py
    """
    print("📧 Gmail Invoice 추출 테스트\n")
    
    try:
        # 테스트 실행 (최근 30일)
        invoices = fetch_invoices(
            search_keywords="Your Replit receipt",
            model="gpt-4o-mini",
            days=30,
            verbose=True
        )
        
        print("\n" + "="*60)
        print("추출된 Invoice 데이터:")
        print("="*60)
        
        for idx, invoice in enumerate(invoices, 1):
            print(f"\n[Invoice {idx}]")
            print(f"  ID: {invoice['invoice_id']}")
            print(f"  날짜: {invoice['date']}")
            print(f"  금액: ${invoice['amount']:.2f}")
            print(f"  서비스: {invoice['service']}")
            print(f"  설명: {invoice['description']}")
            print(f"  기간: {invoice['period']}")
            print(f"  이메일 제목: {invoice['email_subject']}")
        
        print(f"\n✅ 총 {len(invoices)}개 invoice 추출 완료!")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

