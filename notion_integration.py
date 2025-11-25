"""
Notion API 클라이언트
데이터베이스 조회 및 페이지 생성/업데이트
"""
from typing import Dict, Any, List, Optional
from datetime import datetime
from notion_client import Client  # type: ignore
import requests
import config


def format_notion_id(database_id: str) -> str:
    """
    Notion 데이터베이스 ID를 올바른 형식으로 변환
    하이픈이 없으면 추가 (8-4-4-4-12 형식)
    
    Args:
        database_id: 원본 데이터베이스 ID
    
    Returns:
        형식화된 데이터베이스 ID
    """
    # 공백 제거
    database_id = database_id.strip()
    
    # 이미 하이픈이 있으면 그대로 반환 (올바른 형식)
    if "-" in database_id:
        return database_id
    
    # 하이픈 제거
    clean_id = database_id.replace("-", "")
    
    # 32자리 16진수인지 확인
    if len(clean_id) != 32:
        # 32자리가 아니면 원본 반환 (사용자가 입력한 형식 그대로)
        return database_id
    
    # 하이픈 추가 (8-4-4-4-12)
    return f"{clean_id[:8]}-{clean_id[8:12]}-{clean_id[12:16]}-{clean_id[16:20]}-{clean_id[20:]}"


class NotionClient:
    """Notion API 클라이언트"""

    def __init__(self, api_key: str):
        """
        Args:
            api_key: Notion API 키
        """
        self.client = Client(auth=api_key)
        self.api_key = api_key
        self.api_base_url = "https://api.notion.com/v1"
    
    def check_database_exists(self, database_id: str, verbose: bool = False) -> bool:
        """
        데이터베이스 존재 여부 확인
        
        Args:
            database_id: Notion 데이터베이스 ID
            verbose: 상세 디버깅 정보 출력 여부
        
        Returns:
            데이터베이스 존재 여부
        """
        try:
            # ID 형식 변환
            formatted_id = format_notion_id(database_id)
            if verbose:
                print(f"[DEBUG] 원본 데이터베이스 ID: {database_id}")
                print(f"[DEBUG] 형식화된 데이터베이스 ID: {formatted_id}")
                print(f"[DEBUG] 데이터베이스 조회 시도 중...")
            
            response = self.client.databases.retrieve(database_id=formatted_id)
            
            if verbose:
                print(f"[DEBUG] 데이터베이스 조회 성공!")
                db_title = response.get("title", [])
                if db_title:
                    title_text = db_title[0].get("plain_text", "N/A") if isinstance(db_title, list) else "N/A"
                    print(f"[DEBUG] 데이터베이스 제목: {title_text}")
                print(f"[DEBUG] 데이터베이스 속성: {list(response.get('properties', {}).keys())}")
            
            return True
        except Exception as e:
            error_msg = str(e)
            formatted_id = format_notion_id(database_id)
            
            print(f"[ERROR] 데이터베이스 확인 실패: {error_msg}")
            print(f"[DEBUG] 원본 ID: {database_id}")
            print(f"[DEBUG] 형식화된 ID: {formatted_id}")
            print(f"[DEBUG] ID 길이: {len(database_id.replace('-', ''))} (하이픈 제거 후)")
            
            if "Could not find database" in error_msg:
                print(f"[INFO] 해결 방법:")
                print(f"          1. Notion에서 데이터베이스 페이지 열기")
                print(f"          2. 우측 상단 '...' 메뉴 > 'Connections' 선택")
                print(f"          3. Integration을 데이터베이스에 연결")
                print(f"          4. 데이터베이스 ID가 올바른지 확인 (URL에서 추출)")
                print(f"          5. URL 형식: https://www.notion.so/workspace/데이터베이스ID?v=...")
            elif "unauthorized" in error_msg.lower() or "permission" in error_msg.lower():
                print(f"[INFO] 권한 문제일 수 있습니다. Integration이 데이터베이스에 연결되어 있는지 확인하세요.")
            
            if verbose:
                import traceback
                print(f"[DEBUG] 상세 에러:")
                traceback.print_exc()
            
            return False
    
    def find_existing_page(
        self,
        database_id: str,
        date: str,
        model: str,
        time: Optional[str] = None,
        auth_method: Optional[str] = None,
        cost: Optional[float] = None,
        verbose: bool = False
    ) -> tuple[Optional[str], bool]:
        """
        기존 페이지 찾기 (날짜 + 모델 + Key Name + Cost 조합, 시간 정보가 있으면 시간도 고려)

        Args:
            database_id: Notion 데이터베이스 ID
            date: 날짜 (YYYY-MM-DD 형식)
            model: 모델 ID
            time: 시간 정보 (HH:MM:SS 형식, 선택적)
            auth_method: API 키 이름 (Key Name, 선택적)
            cost: 비용 (선택적)
            verbose: 상세 디버깅 정보 출력 여부

        Returns:
            (페이지 ID, Time 업데이트 필요 여부) 튜플
            - 페이지 ID: 없으면 None
            - Time 업데이트 필요: True이면 기존 페이지에 Time이 없고 새 데이터에는 있음
        """
        try:
            # ID 형식 변환
            formatted_id = format_notion_id(database_id)

            if verbose:
                time_info = f", time={time}" if time else ""
                auth_info = f", auth_method={auth_method}" if auth_method else ""
                cost_info = f", cost={cost}" if cost is not None else ""
                print(f"[DEBUG] 중복 체크 시작: date={date}, model={model}{time_info}{auth_info}{cost_info}")

            # 먼저 날짜로만 필터링 (HTTP API 직접 호출)
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
                "Notion-Version": "2022-06-28"
            }

            query_payload = {
                "filter": {
                    "property": "Date",
                    "date": {
                        "equals": date
                    }
                }
            }

            query_url = f"{self.api_base_url}/databases/{formatted_id}/query"
            response = requests.post(query_url, headers=headers, json=query_payload)

            if response.status_code != 200:
                if verbose:
                    print(f"[ERROR] Notion API 쿼리 실패: {response.status_code} - {response.text}")
                return None

            response_data = response.json()
            results = response_data.get("results", [])
            if verbose:
                print(f"[DEBUG] Date={date}로 필터링된 페이지 수: {len(results)}")

            if not results:
                if verbose:
                    print(f"[DEBUG] 해당 날짜에 페이지가 없음 → 중복 아님")
                return None, False

            # 결과에서 모델이 일치하는 페이지 찾기
            for idx, page in enumerate(results):
                properties = page.get("properties", {})
                model_prop = properties.get("Model", {})

                if verbose:
                    print(f"[DEBUG] 페이지 {idx+1} 검사 중...")
                    print(f"[DEBUG]   - Model 필드 타입: {model_prop.get('type')}")

                # Model 필드 타입에 따라 처리
                model_value = None
                if model_prop.get("type") == "title":
                    title = model_prop.get("title", [])
                    if title and len(title) > 0:
                        model_value = title[0].get("plain_text", "")
                elif model_prop.get("type") == "rich_text":
                    rich_text = model_prop.get("rich_text", [])
                    if rich_text and len(rich_text) > 0:
                        model_value = rich_text[0].get("plain_text", "")
                elif model_prop.get("type") == "select":
                    select = model_prop.get("select")
                    if select:
                        model_value = select.get("name", "")

                if verbose:
                    print(f"[DEBUG]   - 추출된 Model 값: '{model_value}'")
                    print(f"[DEBUG]   - 비교 대상 Model: '{model}'")

                # 모델이 일치하는지 확인
                if model_value == model:
                    if verbose:
                        print(f"[DEBUG]   → Model 일치!")

                    # auth_method가 있으면 Key Name도 확인
                    if auth_method:
                        key_name_prop = properties.get("Key Name", {})
                        key_name_value = None
                        if key_name_prop.get("type") == "select":
                            select = key_name_prop.get("select")
                            if select:
                                key_name_value = select.get("name", "")

                        if verbose:
                            print(f"[DEBUG]   - 추출된 Key Name 값: '{key_name_value}'")
                            print(f"[DEBUG]   - 비교 대상 Key Name: '{auth_method}'")

                        # Key Name이 일치하지 않으면 다음 페이지 검사
                        if key_name_value != auth_method:
                            if verbose:
                                print(f"[DEBUG]   → Key Name 불일치, 다음 페이지 검사")
                            continue

                        if verbose:
                            print(f"[DEBUG]   → Key Name 일치!")

                    # cost가 있으면 Cost도 확인
                    if cost is not None:
                        cost_prop = properties.get("Cost ($)", {})
                        cost_value = None
                        if cost_prop.get("type") == "number":
                            cost_value = cost_prop.get("number")

                        if verbose:
                            print(f"[DEBUG]   - 추출된 Cost 값: {cost_value}")
                            print(f"[DEBUG]   - 비교 대상 Cost: {cost}")

                        # Cost가 일치하지 않으면 다음 페이지 검사
                        # 부동소수점 비교는 작은 오차 허용 (0.0001 이내)
                        if cost_value is None or abs(cost_value - cost) > 0.0001:
                            if verbose:
                                print(f"[DEBUG]   → Cost 불일치, 다음 페이지 검사")
                            continue

                        if verbose:
                            print(f"[DEBUG]   → Cost 일치!")

                    # 시간 정보가 있으면 시간도 확인
                    if time:
                        time_prop = properties.get("Time", {})
                        time_value = None
                        if time_prop.get("type") == "rich_text":
                            rich_text = time_prop.get("rich_text", [])
                            if rich_text and len(rich_text) > 0:
                                time_value = rich_text[0].get("plain_text", "")

                        if verbose:
                            print(f"[DEBUG]   - 추출된 Time 값: '{time_value}'")
                            print(f"[DEBUG]   - 비교 대상 Time: '{time}'")

                        # 시간이 일치하면 중복으로 판단
                        if time_value == time:
                            page_id = page.get("id")
                            if verbose:
                                print(f"[DEBUG]   → Time도 일치! 중복 페이지 발견: {page_id}")
                            return page_id, False
                        elif not time_value:
                            # 기존 페이지에 Time이 없고 새 데이터에는 있음 → Time 업데이트 필요
                            page_id = page.get("id")
                            if verbose:
                                print(f"[DEBUG]   → 기존 페이지에 Time 없음, Time 업데이트 필요: {page_id}")
                            return page_id, True
                        else:
                            if verbose:
                                print(f"[DEBUG]   → Time 불일치, 다음 페이지 검사")
                    else:
                        # 시간 정보가 없으면 모델만 일치해도 중복으로 판단
                        page_id = page.get("id")
                        if verbose:
                            print(f"[DEBUG]   → 시간 비교 없음, 중복 페이지 발견: {page_id}")
                        return page_id, False
                else:
                    if verbose:
                        print(f"[DEBUG]   → Model 불일치, 다음 페이지 검사")

            if verbose:
                print(f"[DEBUG] 모든 페이지 검사 완료 → 중복 페이지 없음")
            return None, False
        except Exception as e:
            print(f"[ERROR] 기존 페이지 찾기 실패: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            return None, False
    
    def create_page(
        self,
        database_id: str,
        date: str,
        model: str,
        requests: int,
        quantity: int,
        cost: float,
        unit_price: float,
        api_key: Optional[str] = None,
        time: Optional[str] = None,
        verbose: bool = False
    ) -> Optional[str]:
        """
        새 페이지 생성
        
        Args:
            database_id: Notion 데이터베이스 ID
            date: 날짜 (YYYY-MM-DD 형식)
            model: 모델 ID
            requests: 요청 수
            quantity: 사용량
            cost: 비용
            unit_price: 단가
            api_key: API 키 이름 (select 필드에 사용, 선택적)
            time: 시간 정보 (HH:MM:SS 형식, 선택적)
        
        Returns:
            생성된 페이지 ID (실패 시 None)
        """
        try:
            # ID 형식 변환
            formatted_id = format_notion_id(database_id)
            if verbose:
                print(f"[DEBUG] 데이터베이스 ID: {formatted_id}")
            
            # 날짜 파싱 (시간 없이 날짜만 사용)
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            date_str = date_obj.strftime("%Y-%m-%d")  # YYYY-MM-DD 형식으로 변환
            if verbose:
                if time:
                    print(f"[DEBUG] 날짜: {date} -> {date_str} (시간 정보는 Time 필드에 별도 저장)")
                else:
                    print(f"[DEBUG] 날짜: {date} -> {date_str} (시간 제외, 날짜만)")
            
            # 페이지 속성 구성
            properties = {
                "Date": {
                    "date": {
                        "start": date_str
                    }
                },
                "Model": {
                    "title": [
                        {
                            "text": {
                                "content": model
                            }
                        }
                    ]
                },
                "Model List": {
                    "select": {
                        "name": model
                    }
                },
                "Requests": {
                    "number": requests
                },
                "Quantity": {
                    "number": quantity
                },
                "Cost ($)": {
                    "number": cost
                },
                "Unit Price ($)": {
                    "number": unit_price
                }
            }
            
            # Key Name select 필드 추가 (있으면)
            if api_key:
                properties["Key Name"] = {
                    "select": {
                        "name": api_key
                    }
                }
            
            # 시간 정보가 있으면 Time 필드 추가
            if time:
                properties["Time"] = {
                    "rich_text": [
                        {
                            "text": {
                                "content": time
                            }
                        }
                    ]
                }
            
            if verbose:
                print(f"[DEBUG] 페이지 속성:")
                if time:
                    print(f"  - Date: {date_str} (날짜만, 시간은 Time 필드에 별도 저장)")
                    print(f"  - Time: {time}")
                else:
                    print(f"  - Date: {date_str} (날짜만)")
                print(f"  - Model: {model} (title 타입)")
                print(f"  - Model List: {model} (select 타입, 자동 생성)")
                if api_key:
                    print(f"  - Key Name: {api_key} (select 타입, 자동 생성)")
                print(f"  - Requests: {requests}")
                print(f"  - Quantity: {quantity}")
                print(f"  - Cost: {cost}")
                print(f"  - Unit Price: {unit_price}")
            
            # 페이지 생성
            if verbose:
                print(f"[DEBUG] Notion API 호출 중...")
            response = self.client.pages.create(
                parent={"database_id": formatted_id},
                properties=properties
            )
            
            page_id = response.get("id")
            if verbose:
                print(f"[DEBUG] 페이지 생성 성공! 페이지 ID: {page_id}")
            
            return page_id
        except Exception as e:
            import traceback
            error_msg = str(e)
            print(f"[ERROR] Notion 페이지 생성 실패: {error_msg}")
            
            if verbose:
                print(f"[DEBUG] 상세 에러 정보:")
                traceback.print_exc()
                print(f"[DEBUG] 입력 데이터:")
                print(f"  - database_id: {database_id}")
                print(f"  - date: {date}")
                print(f"  - time: {time}")
                print(f"  - model: {model}")
                print(f"  - requests: {requests}")
                print(f"  - quantity: {quantity}")
                print(f"  - cost: {cost}")
                print(f"  - unit_price: {unit_price}")
            
            # 특정 에러 타입에 대한 안내
            if "property" in error_msg.lower() and "does not exist" in error_msg.lower():
                print(f"[INFO] 필드 이름이 데이터베이스에 존재하지 않습니다.")
                required_fields = "Date, Model, Model List, Requests, Quantity, Cost ($), Unit Price ($)"
                if api_key:
                    required_fields += ", Key Name"
                print(f"[INFO] 필수 필드: {required_fields}")
                print(f"[INFO] 필드 이름은 대소문자와 공백을 정확히 일치시켜야 합니다.")
            elif "validation" in error_msg.lower():
                print(f"[INFO] 필드 타입이 올바르지 않을 수 있습니다.")
                print(f"[INFO] Date는 Date 타입, Model은 Title 타입, Model List와 Key Name는 Select 타입, Time은 Rich Text 타입, 나머지는 Number 타입이어야 합니다.")
                print(f"[INFO] Model List와 Key Name 필드가 Select 타입인지 확인하세요. 새로운 옵션은 자동으로 생성됩니다.")
            
            return None
    
    def update_page(
        self,
        page_id: str,
        requests: int,
        quantity: int,
        cost: float,
        unit_price: float,
        time: Optional[str] = None,
        time_only: bool = False
    ) -> bool:
        """
        기존 페이지 업데이트

        Args:
            page_id: Notion 페이지 ID
            requests: 요청 수
            quantity: 사용량
            cost: 비용
            unit_price: 단가
            time: 시간 정보 (HH:MM:SS 형식, 선택적)
            time_only: True이면 Time 필드만 업데이트

        Returns:
            업데이트 성공 여부
        """
        try:
            if time_only and time:
                # Time 필드만 업데이트
                properties = {
                    "Time": {
                        "rich_text": [
                            {
                                "text": {
                                    "content": time
                                }
                            }
                        ]
                    }
                }
            else:
                # 전체 필드 업데이트
                properties = {
                    "Requests": {
                        "number": requests
                    },
                    "Quantity": {
                        "number": quantity
                    },
                    "Cost ($)": {
                        "number": cost
                    },
                    "Unit Price ($)": {
                        "number": unit_price
                    }
                }

                # 시간 정보가 있으면 Time 필드도 업데이트
                if time:
                    properties["Time"] = {
                        "rich_text": [
                            {
                                "text": {
                                    "content": time
                                }
                            }
                        ]
                    }

            self.client.pages.update(page_id=page_id, properties=properties)
            return True
        except Exception as e:
            print(f"[ERROR] Notion 페이지 업데이트 실패: {e}")
            return False
    
    def save_usage_data(
        self,
        database_id: str,
        records: List[Dict[str, Any]],
        update_existing: bool = False,
        verbose: bool = False
    ) -> Dict[str, int]:
        """
        사용량 데이터를 Notion에 저장
        
        Args:
            database_id: Notion 데이터베이스 ID
            records: 저장할 데이터 리스트 (각 항목은 date, model, requests, quantity, cost, unit_price 포함)
            update_existing: 기존 페이지가 있으면 업데이트할지 여부
            verbose: 상세 디버깅 정보 출력 여부
        
        Returns:
            {"created": 생성된 개수, "updated": 업데이트된 개수, "skipped": 스킵된 개수}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}
        
        if not records:
            print("[WARNING] 저장할 레코드가 없습니다.")
            return stats
        
        formatted_id = format_notion_id(database_id)
        if verbose:
            print(f"[DEBUG] 저장할 레코드 수: {len(records)}")
            print(f"[DEBUG] 데이터베이스 ID: {formatted_id}")
        
        for idx, record in enumerate(records, 1):
            if verbose:
                print(f"\n[DEBUG] 레코드 {idx}/{len(records)} 처리 중...")
                print(f"[DEBUG] 레코드 내용: {record}")
            date = record.get("date")
            model = record.get("model")
            time = record.get("time")  # 시간 정보 추출 (시/분 단위일 때만 존재)
            auth_method = record.get("auth_method")  # API 키 이름 추출
            requests = record.get("requests", 0)
            quantity = record.get("quantity", 0)
            cost = record.get("cost", 0.0)
            unit_price = record.get("unit_price", 0.0)

            if not date or not model:
                if verbose:
                    print(f"[WARNING] 날짜 또는 모델이 없어서 스킵: date={date}, model={model}")
                stats["skipped"] += 1
                continue

            # 기존 페이지 확인
            if verbose:
                time_info = f", time={time}" if time else ""
                auth_info = f", auth_method={auth_method}" if auth_method else ""
                cost_info = f", cost={cost}" if cost else ""
                print(f"[DEBUG] 기존 페이지 확인 중: date={date}, model={model}{time_info}{auth_info}{cost_info}")
            existing_page_id, needs_time_update = self.find_existing_page(
                database_id, date, model, time=time, auth_method=auth_method, cost=cost, verbose=verbose
            )

            if existing_page_id:
                if verbose:
                    print(f"[DEBUG] 기존 페이지 발견: {existing_page_id}")
                    if needs_time_update:
                        print(f"[DEBUG] Time 업데이트 필요!")

                # Time만 업데이트하는 경우
                if needs_time_update and time:
                    if verbose:
                        print(f"[DEBUG] Time 필드만 업데이트 시도 중...")
                    if self.update_page(existing_page_id, requests, quantity, cost, unit_price, time=time, time_only=True):
                        time_info = f" ({time})" if time else ""
                        print(f"[INFO] Time 필드 추가: {date}{time_info} - {model}")
                        if verbose:
                            print(f"[DEBUG] Time 업데이트 성공!")
                        stats["updated"] += 1
                    else:
                        if verbose:
                            print(f"[DEBUG] Time 업데이트 실패")
                        stats["skipped"] += 1
                # 전체 업데이트하는 경우
                elif update_existing:
                    if verbose:
                        print(f"[DEBUG] 페이지 전체 업데이트 시도 중...")
                    if self.update_page(existing_page_id, requests, quantity, cost, unit_price, time=time):
                        if verbose:
                            print(f"[DEBUG] 페이지 업데이트 성공!")
                        stats["updated"] += 1
                    else:
                        if verbose:
                            print(f"[DEBUG] 페이지 업데이트 실패")
                        stats["skipped"] += 1
                # 중복 데이터 스킵
                else:
                    time_info = f" ({time})" if time else ""
                    print(f"[INFO] 중복 데이터 스킵: {date}{time_info} - {model}")
                    if verbose:
                        print(f"[DEBUG] 기존 페이지 ID: {existing_page_id}")
                        print(f"[DEBUG] update_existing=False이므로 스킵합니다.")
                    stats["skipped"] += 1
            else:
                if verbose:
                    print(f"[DEBUG] 새 페이지 생성 시도 중...")
                # 새로 생성
                page_id = self.create_page(
                    database_id, date, model, requests, quantity, cost, unit_price,
                    api_key=auth_method, time=time, verbose=verbose
                )
                if page_id:
                    if verbose:
                        print(f"[DEBUG] 페이지 생성 성공: {page_id}")
                    stats["created"] += 1
                else:
                    if verbose:
                        print(f"[DEBUG] 페이지 생성 실패")
                    stats["skipped"] += 1
        
        return stats
    
    def create_invoice_page(
        self,
        database_id: str,
        invoice_id: str,
        date: str,
        amount: float,
        description: str,
        period: str,
        service: str,
        email_subject: str,
        paid_status: str = "Paid",
        verbose: bool = False
    ) -> Optional[str]:
        """
        Invoice 페이지 생성
        
        Args:
            database_id: Notion 데이터베이스 ID
            invoice_id: Invoice Number
            date: Date Paid (YYYY-MM-DD)
            amount: 금액 (USD)
            description: 설명
            period: 청구 기간
            service: 서비스명 (자동으로 Select 옵션 생성됨)
            email_subject: 이메일 제목
            paid_status: 결제 상태 (Paid, Unpaid, Pending 등, 자동으로 Status 옵션 생성됨)
            verbose: 디버그 로그 출력
        
        Returns:
            생성된 페이지 ID (실패 시 None)
        """
        try:
            formatted_id = format_notion_id(database_id)
            
            if verbose:
                print(f"[DEBUG] Invoice 페이지 생성 중: {invoice_id}")
            
            # 날짜 파싱
            date_obj = datetime.strptime(date, "%Y-%m-%d")
            date_str = date_obj.strftime("%Y-%m-%d")
            
            # 페이지 속성 구성
            properties = {
                "Invoice Number": {
                    "title": [
                        {
                            "text": {
                                "content": invoice_id
                            }
                        }
                    ]
                },
                "Date Paid": {
                    "date": {
                        "start": date_str
                    }
                },
                "Amount ($)": {
                    "number": amount
                },
                "Service": {
                    "select": {
                        "name": service
                    }
                },
                "Description": {
                    "rich_text": [
                        {
                            "text": {
                                "content": description
                            }
                        }
                    ]
                },
                "Period": {
                    "rich_text": [
                        {
                            "text": {
                                "content": period
                            }
                        }
                    ]
                },
                "Email Subject": {
                    "rich_text": [
                        {
                            "text": {
                                "content": email_subject
                            }
                        }
                    ]
                },
                "Paid Status": {
                    "status": {
                        "name": paid_status
                    }
                }
            }
            
            if verbose:
                print(f"[DEBUG] Invoice 속성:")
                print(f"  - Invoice ID: {invoice_id}")
                print(f"  - Date: {date_str}")
                print(f"  - Amount: ${amount:.2f}")
                print(f"  - Service: {service}")
                print(f"  - Paid Status: {paid_status}")
            
            # 페이지 생성
            response = self.client.pages.create(
                parent={"database_id": formatted_id},
                properties=properties
            )
            
            page_id = response.get("id")
            if verbose:
                print(f"[DEBUG] Invoice 페이지 생성 성공: {page_id}")
            
            return page_id
            
        except Exception as e:
            print(f"[ERROR] Invoice 페이지 생성 실패: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            return None
    
    def find_existing_invoice(
        self,
        database_id: str,
        invoice_id: str,
        verbose: bool = False
    ) -> Optional[str]:
        """
        기존 Invoice 페이지 찾기 (Invoice Number 기준)
        
        Args:
            database_id: Notion 데이터베이스 ID
            invoice_id: Invoice Number
            verbose: 디버그 로그 출력
        
        Returns:
            페이지 ID (없으면 None)
        """
        try:
            formatted_id = format_notion_id(database_id)
            
            if verbose:
                print(f"[DEBUG] Invoice 중복 체크: {invoice_id}")
            
            # HTTP API 직접 호출로 검색
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-type": "application/json",
                "Notion-Version": "2022-06-28"
            }
            
            query_payload = {
                "filter": {
                    "property": "Invoice Number",
                    "title": {
                        "equals": invoice_id
                    }
                }
            }
            
            query_url = f"{self.api_base_url}/databases/{formatted_id}/query"
            response = requests.post(query_url, headers=headers, json=query_payload)
            
            if response.status_code != 200:
                if verbose:
                    print(f"[ERROR] Notion API 쿼리 실패: {response.status_code}")
                return None
            
            response_data = response.json()
            results = response_data.get("results", [])
            
            if results:
                page_id = results[0].get("id")
                if verbose:
                    print(f"[DEBUG] 기존 Invoice 발견: {page_id}")
                return page_id
            
            if verbose:
                print(f"[DEBUG] 중복 Invoice 없음")
            
            return None
            
        except Exception as e:
            print(f"[ERROR] Invoice 검색 실패: {e}")
            if verbose:
                import traceback
                traceback.print_exc()
            return None
    
    def save_invoices(
        self,
        database_id: str,
        invoices: List[Dict[str, Any]],
        update_existing: bool = False,
        verbose: bool = False
    ) -> Dict[str, int]:
        """
        Invoice 데이터를 Notion에 저장
        
        Args:
            database_id: Notion 데이터베이스 ID
            invoices: Invoice 데이터 리스트
            update_existing: 중복 시 업데이트 여부
            verbose: 디버그 로그 출력
        
        Returns:
            {"created": 생성 수, "updated": 업데이트 수, "skipped": 스킵 수}
        """
        stats = {"created": 0, "updated": 0, "skipped": 0}
        
        if not invoices:
            print("[WARNING] 저장할 Invoice가 없습니다.")
            return stats
        
        formatted_id = format_notion_id(database_id)
        if verbose:
            print(f"[DEBUG] Invoice 저장 시작: {len(invoices)}개")
            print(f"[DEBUG] 데이터베이스 ID: {formatted_id}")
        
        for idx, invoice in enumerate(invoices, 1):
            if verbose:
                print(f"\n[DEBUG] Invoice {idx}/{len(invoices)} 처리 중...")
            
            invoice_id = invoice.get("invoice_id")
            date = invoice.get("date")
            amount = invoice.get("amount")
            description = invoice.get("description", "N/A")
            period = invoice.get("period", "N/A")
            service = invoice.get("service", "Unknown")
            email_subject = invoice.get("email_subject", "N/A")
            paid_status = invoice.get("paid_status", "Paid")
            
            if not invoice_id or not date:
                if verbose:
                    print(f"[WARNING] 필수 필드 누락, 스킵")
                stats["skipped"] += 1
                continue
            
            # 기존 Invoice 확인
            existing_page_id = self.find_existing_invoice(database_id, invoice_id, verbose)
            
            if existing_page_id:
                if update_existing:
                    if verbose:
                        print(f"[DEBUG] 업데이트 모드: 기존 페이지 유지")
                    # TODO: Invoice 업데이트 로직 (필요시 구현)
                    stats["skipped"] += 1
                else:
                    print(f"[INFO] 중복 Invoice 스킵: {invoice_id}")
                    if verbose:
                        print(f"[DEBUG] 기존 페이지 ID: {existing_page_id}")
                    stats["skipped"] += 1
            else:
                # 새로 생성
                page_id = self.create_invoice_page(
                    database_id=database_id,
                    invoice_id=invoice_id,
                    date=date,
                    amount=amount,
                    description=description,
                    period=period,
                    service=service,
                    email_subject=email_subject,
                    paid_status=paid_status,
                    verbose=verbose
                )
                
                if page_id:
                    if verbose:
                        print(f"[DEBUG] Invoice 생성 성공")
                    stats["created"] += 1
                else:
                    if verbose:
                        print(f"[DEBUG] Invoice 생성 실패")
                    stats["skipped"] += 1
        
        if verbose:
            print(f"\n[완료] Created: {stats['created']}, Skipped: {stats['skipped']}")
        
        return stats

