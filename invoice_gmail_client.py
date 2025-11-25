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
    search_keywords: Optional[List[str]] = None,
    model: str = "gpt-4o-mini",
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    days: int = 90,
    verbose: bool = False,
    openai_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Gmail에서 invoice 메일을 검색하고 구조화된 데이터로 추출 (다중 키워드 지원)
    
    Args:
        search_keywords: Gmail 검색 키워드 리스트 (None이면 config에서 가져옴)
        model: OpenAI 모델 (gpt-4o 또는 gpt-4o-mini)
        start_date: 검색 시작 날짜 (YYYY-MM-DD, None이면 days 사용)
        end_date: 검색 종료 날짜 (YYYY-MM-DD, None이면 오늘)
        days: start_date가 None일 때 최근 N일 검색 (기본: 90일)
        verbose: 상세 로그 출력
        openai_api_key: OpenAI API 키 (None이면 config 또는 환경 변수에서 가져옴)
    
    Returns:
        List[Dict]: Invoice 데이터 리스트 (모든 키워드의 결과 합침)
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
    # 검색 키워드 가져오기 및 정규화
    if search_keywords is None:
        search_keywords = config.get_invoice_search_keywords()
    elif isinstance(search_keywords, str):
        # 문자열이면 리스트로 변환 (하위 호환성)
        search_keywords = [search_keywords]
    
    if not search_keywords:
        raise ValueError("검색 키워드가 비어있습니다.")
    
    if verbose:
        print(f"[DEBUG] 검색 키워드: {search_keywords} ({len(search_keywords)}개)")
    
    # 여러 키워드로 검색
    all_invoices = []
    seen_invoice_ids = set()
    
    for idx, keyword in enumerate(search_keywords, 1):
        if verbose:
            print(f"\n{'='*60}")
            print(f"[키워드 {idx}/{len(search_keywords)}] '{keyword}' 검색 중...")
            print(f"{'='*60}")
        
        try:
            invoices = _fetch_invoices_single_keyword(
                keyword=keyword,
                model=model,
                start_date=start_date,
                end_date=end_date,
                days=days,
                openai_api_key=openai_api_key,
                verbose=verbose
            )
            
            # 중복 제거 (invoice_id 기준)
            for invoice in invoices:
                invoice_id = invoice.get("invoice_id")
                if invoice_id not in seen_invoice_ids:
                    seen_invoice_ids.add(invoice_id)
                    all_invoices.append(invoice)
                elif verbose:
                    print(f"[DEBUG] 중복 Invoice 스킵: {invoice_id}")
            
            if verbose:
                print(f"✓ '{keyword}': {len(invoices)}개 발견 (중복 제거 후 총 {len(all_invoices)}개)")
        
        except Exception as e:
            print(f"[ERROR] '{keyword}' 검색 실패: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            continue
    
    if verbose:
        print(f"\n{'='*60}")
        print(f"[최종 결과] 총 {len(all_invoices)}개 Invoice (중복 제거 완료)")
        print(f"{'='*60}\n")
    
    return all_invoices


def _fetch_invoices_single_keyword(
    keyword: str,
    model: str,
    start_date: Optional[str],
    end_date: Optional[str],
    days: int,
    verbose: bool,
    openai_api_key: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    단일 검색 키워드로 invoice 검색 (내부 헬퍼 함수)
    """
    try:
        from openai import OpenAI
    except ImportError:
        raise ImportError(
            "❌ openai 패키지가 필요합니다.\n"
            "설치: pip install openai"
        )
    
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
    api_key = config.get_openai_api_key(openai_api_key)
    if not api_key:
        raise ValueError(
            "OpenAI API 키가 필요합니다.\n"
            "환경 변수 OPENAI_API_KEY를 설정하거나 config.json에 추가하거나 -open-ai-api-key 옵션을 사용하세요."
        )
    
    # OpenAI 클라이언트 생성
    client = OpenAI(api_key=api_key)
    
    # 프롬프트 생성
    prompt = _create_extraction_prompt(keyword, start_date, end_date)
    
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


def _create_extraction_prompt(search_keyword: str, start_date: str, end_date: str) -> str:
    """Invoice 추출 프롬프트 생성"""
    # Gmail 날짜 형식으로 변환 (YYYY/MM/DD)
    gmail_start = start_date.replace("-", "/")
    gmail_end = end_date.replace("-", "/")
    
    return f"""
Search Gmail for emails matching: "{search_keyword}"

Date range: after:{gmail_start} before:{gmail_end}

For each invoice email found, extract the following information and return as a JSON array:

[
  {{
    "invoice_id": "string (invoice number - extract from invoice body, NOT receipt number)",
    "date": "YYYY-MM-DD (date paid from invoice, if not found use email date)",
    "amount": number (total amount in USD, numeric only without $ symbol)",
    "description": "string (brief description of charges/services)",
    "period": "string (billing period if mentioned, e.g., 'Jan 1-31, 2024' or 'N/A')",
    "service": "string (service/company name, e.g., 'Replit', 'AWS', etc.)",
    "email_subject": "string (original email subject line)",
    "paid_status": "string (payment status: 'Paid', 'Unpaid', 'Pending', 'Overdue', etc.)"
  }}
]

Important extraction rules:
1. Return ONLY valid JSON array, no markdown code blocks
2. If no invoice emails found, return empty array: []
3. "invoice_id" MUST be the invoice number (not receipt number) - look for "Invoice Number:", "Invoice #:", etc. in email body
4. If invoice number is not found, use pattern: "INV-YYYY-MM-DD" based on invoice date
5. "amount" must be a number (not string), extract numeric value only
6. "date" must be in YYYY-MM-DD format - use invoice date paid if available, otherwise use email sent date
7. "period" should capture billing period if mentioned in email, otherwise use "N/A"
8. "service" should identify the service provider from email sender or content (e.g., "Replit", "AWS", "Google Cloud")
   - Use simple company/service names without special punctuation
   - If company name contains commas (e.g., "Anthropic, PBC"), use without comma (e.g., "Anthropic PBC" or "Anthropic")
9. "paid_status" should determine payment status - if it's a receipt/confirmation email, use "Paid"; if it mentions "pending" or "due", use "Unpaid" or "Pending"
10. Extract data accurately from email body, subject, and metadata
11. Focus on invoice/receipt/billing emails only, ignore other types

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
    
    # Service 이름 정제 (콤마를 하이픈으로 치환 - Notion Select 필드 호환성)
    service_name = str(invoice["service"]).strip()
    # 콤마를 " -"로 치환하여 하나의 서비스로 유지 (예: "anthropic, pbc" → "anthropic - pbc")
    service_name = service_name.replace(",", " -")

    # 정제된 데이터 반환
    return {
        "invoice_id": str(invoice["invoice_id"]).strip(),
        "date": invoice["date"],
        "amount": float(invoice["amount"]),
        "description": str(invoice.get("description", "N/A")).strip(),
        "period": str(invoice.get("period", "N/A")).strip(),
        "service": service_name,
        "email_subject": str(invoice.get("email_subject", "N/A")).strip(),
        "paid_status": str(invoice.get("paid_status", "Paid")).strip()
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
            "email_subject": invoice["email_subject"],
            "paid_status": invoice["paid_status"]
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
            search_keywords=["Your Replit receipt"],
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
            print(f"  결제 상태: {invoice['paid_status']}")
            print(f"  설명: {invoice['description']}")
            print(f"  기간: {invoice['period']}")
            print(f"  이메일 제목: {invoice['email_subject']}")
        
        print(f"\n✅ 총 {len(invoices)}개 invoice 추출 완료!")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

