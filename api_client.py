"""
fal.ai API 클라이언트
Usage API 호출 및 페이지네이션 처리
"""
import requests  # type: ignore
import time
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo
import date_utils
import config


BASE_URL = "https://api.fal.ai/v1/models"
USAGE_ENDPOINT = f"{BASE_URL}/usage"


def extract_date_range_from_time_series(
    time_series: List[Dict[str, Any]], 
    target_timezone: Optional[str] = None,
    timeframe: Optional[str] = None,
    bound_to_timeframe: bool = True
) -> Tuple[Optional[str], Optional[str]]:
    """
    time_series 데이터에서 bucket 필드를 분석하여 실제 데이터가 있는 기간 추출
    bucket의 실제 최소/최대 값을 그대로 사용하여 데이터 신뢰성 유지
    bucket은 UTC 시간이므로 사용자 타임존으로 변환
    
    Args:
        time_series: time_series 데이터 리스트 [{"bucket": "...", "results": [...]}, ...]
        target_timezone: 변환할 타임존 (None이면 UTC 그대로)
        timeframe: 집계 단위 (minute, hour, day, week, month) - 참고용
        bound_to_timeframe: timeframe 경계 정렬 여부 - 참고용
    
    Returns:
        (시작 날짜 ISO8601 문자열, 종료 날짜 ISO8601 문자열) 튜플
        bucket이 없으면 (None, None) 반환
    """
    if not time_series or not isinstance(time_series, list):
        return None, None
    
    buckets = []
    for entry in time_series:
        if not isinstance(entry, dict):
            continue
        bucket = entry.get("bucket")
        if bucket and isinstance(bucket, str):
            try:
                # bucket을 datetime으로 파싱 (UTC로 가정)
                # ISO8601 형식: "2024-01-01T00:00:00Z" 또는 "2024-01-01T00:00:00+00:00"
                bucket_str = bucket.replace('Z', '+00:00')
                dt = datetime.fromisoformat(bucket_str)
                # UTC로 명시적으로 설정 (타임존 정보가 없으면 UTC로 가정)
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                else:
                    # 이미 타임존이 있으면 UTC로 변환
                    dt = dt.astimezone(timezone.utc)
                
                # 사용자 타임존으로 변환
                if target_timezone:
                    try:
                        target_tz = ZoneInfo(target_timezone)
                        dt = dt.astimezone(target_tz)
                    except Exception:
                        # 타임존 변환 실패 시 UTC 그대로 사용
                        pass
                
                buckets.append(dt)
            except (ValueError, AttributeError):
                # 파싱 실패 시 무시
                continue
    
    if not buckets:
        return None, None
    
    # 가장 오래된 날짜와 가장 최근 날짜 찾기
    # bucket의 실제 값을 그대로 사용
    min_bucket = min(buckets)
    max_bucket = max(buckets)
    
    # ISO8601 형식으로 변환
    min_str = min_bucket.isoformat()
    max_str = max_bucket.isoformat()
    
    return min_str, max_str


class FalAPIClient:
    """fal.ai API 클라이언트"""
    
    def __init__(self, api_key: str):
        """
        Args:
            api_key: fal.ai Admin API 키
        """
        self.api_key = api_key
        self.headers = {
            "Authorization": f"Key {api_key}",
            "Content-Type": "application/json"
        }
    
    def get_usage(
        self,
        endpoint_ids: List[str],
        start: Optional[datetime] = None,
        end: Optional[datetime] = None,
        timeframe: Optional[str] = None,
        timezone: Optional[str] = None,
        expand: Optional[List[str]] = None,
        bound_to_timeframe: bool = True,
        include_notion: bool = False
    ) -> Dict[str, Any]:
        """
        Usage API 호출 (페이지네이션 자동 처리)
        
        Args:
            endpoint_ids: 모델 ID 목록 (1-50개)
            start: 시작 날짜 (datetime 객체)
            end: 종료 날짜 (datetime 객체)
            timeframe: 집계 단위 (minute, hour, day, week, month)
            timezone: 타임존 (기본값: config에서 가져옴)
            bound_to_timeframe: timeframe 경계 정렬 (기본값: True)
            expand: expand 파라미터 목록 (자동 설정 시 None)
            include_notion: Notion 저장 여부 (expand 자동 설정용)
        
        Returns:
            API 응답 데이터 (모든 페이지 통합)
        """
        if not endpoint_ids:
            raise ValueError("최소 1개의 endpoint_id가 필요합니다.")
        
        if len(endpoint_ids) > 50:
            raise ValueError("endpoint_id는 최대 50개까지 지정할 수 있습니다.")
        
        # 타임존 기본값
        if not timezone:
            timezone = config.get_timezone()
        
        # expand 파라미터 설정
        if expand is None:
            if include_notion:
                # Notion 저장 시: 날짜별 상세 데이터 필요
                expand = ["time_series", "auth_method"]
            else:
                # 일반 조회 시: 요약 데이터만
                expand = ["summary", "auth_method"]
        
        # 날짜 범위 기본값 처리
        if not start or not end:
            start, end = date_utils.get_default_date_range(timezone)
        
        # ISO8601 형식으로 변환
        start_str, end_str = date_utils.format_date_range_for_api(start, end, include_time=True)
        
        # 모델이 2개 이하일 때는 한 번에 호출, 3개 이상일 때는 개별 호출
        # (API가 3개 이상의 모델을 한 번에 처리하지 못하는 경우 대비)
        if len(endpoint_ids) <= 2:
            return self._get_usage_single(endpoint_ids, start_str, end_str, timeframe, timezone, expand, bound_to_timeframe)
        else:
            # 각 모델을 개별적으로 호출하고 결과 합치기
            all_summaries = []
            all_time_series = []
            
            for i, endpoint_id in enumerate(endpoint_ids):
                result = self._get_usage_single([endpoint_id], start_str, end_str, timeframe, timezone, expand, bound_to_timeframe)
                
                # summary 데이터 합치기 (result에서 직접 추출)
                summary = result.get("summary")
                if isinstance(summary, list):
                    all_summaries.extend(summary)
                elif summary:
                    all_summaries.append(summary)
                
                # time_series 데이터 합치기 (result에서 직접 추출)
                time_series = result.get("time_series")
                if isinstance(time_series, list):
                    all_time_series.extend(time_series)
                elif time_series:
                    all_time_series.append(time_series)
                
                # Rate Limit 방지를 위해 마지막 호출이 아니면 지연 시간 추가
                if i < len(endpoint_ids) - 1:
                    time.sleep(0.5)  # 0.5초 지연
            
            # time_series에서 실제 조회 기간 추출 (bound_to_timeframe이 적용된 경우)
            # bucket은 UTC이므로 사용자 타임존으로 변환
            actual_start = start_str
            actual_end = end_str
            if all_time_series:
                bucket_start, bucket_end = extract_date_range_from_time_series(
                    all_time_series, 
                    timezone, 
                    timeframe, 
                    bound_to_timeframe
                )
                if bucket_start and bucket_end:
                    actual_start = bucket_start
                    actual_end = bucket_end
            
            # 최종 응답 구성
            result = {
                "summary": all_summaries,
                "time_series": all_time_series,
                "next_cursor": None,
                "has_more": False,
                "_meta": {
                    "start": actual_start,  # bucket에서 추출한 실제 조회 기간 사용
                    "end": actual_end,      # bucket에서 추출한 실제 조회 기간 사용
                    "timezone": timezone,
                    "timeframe": timeframe,
                    "endpoint_ids": endpoint_ids,
                    "expand": expand if isinstance(expand, list) else expand.split(",") if expand else []
                }
            }
            
            return result
    
    def _get_usage_single(
        self,
        endpoint_ids: List[str],
        start_str: str,
        end_str: str,
        timeframe: Optional[str],
        timezone: str,
        expand: List[str],
        bound_to_timeframe: bool
    ) -> Dict[str, Any]:
        """단일 API 호출 (내부 메서드)"""
        # 파라미터 구성
        params = {
            "endpoint_id": ",".join(endpoint_ids),  # 쉼표 구분 형식
            "start": start_str,
            "end": end_str,
            "timezone": timezone,
            "bound_to_timeframe": str(bound_to_timeframe).lower(),
            "expand": ",".join(expand) if isinstance(expand, list) else expand
        }
        
        # timeframe이 지정된 경우만 추가
        if timeframe:
            params["timeframe"] = timeframe
        
        # 첫 번째 요청
        all_data = []
        cursor = None
        has_more = True
        
        while has_more:
            # cursor가 있으면 파라미터에 추가
            if cursor:
                params["cursor"] = cursor
            
            # API 호출 (Rate Limit 재시도 포함)
            max_retries = 3
            retry_delay = 1.0  # 초기 재시도 지연 시간 (초)
            
            for attempt in range(max_retries):
                response = requests.get(USAGE_ENDPOINT, headers=self.headers, params=params)
                
                # 429 Rate Limit 에러인 경우 재시도
                if response.status_code == 429:
                    if attempt < max_retries - 1:
                        # Retry-After 헤더가 있으면 사용, 없으면 지수 백오프
                        retry_after = response.headers.get("Retry-After")
                        if retry_after:
                            wait_time = float(retry_after)
                        else:
                            wait_time = retry_delay * (2 ** attempt)  # 지수 백오프
                        
                        time.sleep(wait_time)
                        continue
                    else:
                        # 최대 재시도 횟수 초과
                        error_msg = f"API 호출 실패: {response.status_code} (Rate Limit, 재시도 횟수 초과)"
                        try:
                            error_data = response.json()
                            if "detail" in error_data:
                                error_msg += f" - {error_data['detail']}"
                        except:
                            error_msg += f" - {response.text}"
                        raise requests.exceptions.HTTPError(error_msg)
                
                # 다른 에러 처리
                if response.status_code != 200:
                    error_msg = f"API 호출 실패: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "detail" in error_data:
                            error_msg += f" - {error_data['detail']}"
                    except:
                        error_msg += f" - {response.text}"
                    raise requests.exceptions.HTTPError(error_msg)
                
                # 성공한 경우 루프 종료
                break
            
            data = response.json()
            
            # 데이터 수집
            # 응답 구조에 따라 다를 수 있으므로 유연하게 처리
            if isinstance(data, dict):
                # items 또는 data 필드가 있는 경우
                items = data.get("items", data.get("data", []))
                if items:
                    all_data.extend(items)
                else:
                    # items가 없으면 전체 응답을 추가
                    all_data.append(data)
                
                # 페이지네이션 정보 확인
                # has_more와 next_cursor는 항상 response에 존재
                has_more = data.get("has_more", False)
                
                # has_more가 true일 때만 next_cursor가 유효한 값
                # has_more가 false이면 next_cursor는 null
                if has_more:
                    cursor = data.get("next_cursor")
                else:
                    cursor = None
            else:
                # 리스트 형식인 경우
                all_data.extend(data)
                has_more = False
                cursor = None
        
        # 최종 응답 구성
        # all_data가 비어있거나 리스트인 경우 항상 딕셔너리로 래핑
        if not all_data:
            result = {
                "items": [],
                "total_count": 0
            }
        elif len(all_data) == 1 and isinstance(all_data[0], dict):
            # 단일 딕셔너리인 경우
            result = all_data[0]
            # _meta가 이미 있으면 유지, 없으면 추가
            if "_meta" not in result:
                result["_meta"] = {}
        else:
            # 여러 항목인 경우 items로 래핑
            result = {
                "items": all_data,
                "total_count": len(all_data)
            }
        
        # time_series에서 실제 조회 기간 추출 (bound_to_timeframe이 적용된 경우)
        # bucket은 UTC이므로 사용자 타임존으로 변환
        actual_start = start_str
        actual_end = end_str
        time_series = result.get("time_series", [])
        if time_series:
            bucket_start, bucket_end = extract_date_range_from_time_series(
                time_series, 
                timezone, 
                timeframe, 
                bound_to_timeframe
            )
            if bucket_start and bucket_end:
                actual_start = bucket_start
                actual_end = bucket_end
        
        # 메타데이터 추가/업데이트
        if "_meta" not in result:
            result["_meta"] = {}
        result["_meta"].update({
            "start": actual_start,  # bucket에서 추출한 실제 조회 기간 사용
            "end": actual_end,      # bucket에서 추출한 실제 조회 기간 사용
            "timezone": timezone,
            "timeframe": timeframe,
            "endpoint_ids": endpoint_ids,
            "expand": expand if isinstance(expand, list) else expand.split(",") if expand else []
        })
        
        return result
    
    def get_pricing(
        self,
        endpoint_ids: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Pricing API 호출 (모델별 가격 정보)
        
        Args:
            endpoint_ids: 모델 ID 목록 (None이면 전체)
        
        Returns:
            가격 정보 데이터
        """
        pricing_endpoint = f"{BASE_URL}/pricing"
        
        params = {}
        if endpoint_ids:
            params["endpoint_id"] = ",".join(endpoint_ids)
        
        response = requests.get(pricing_endpoint, headers=self.headers, params=params)
        
        if response.status_code != 200:
            error_msg = f"Pricing API 호출 실패: {response.status_code}"
            try:
                error_data = response.json()
                if "detail" in error_data:
                    error_msg += f" - {error_data['detail']}"
            except:
                error_msg += f" - {response.text}"
            raise requests.exceptions.HTTPError(error_msg)
        
        return response.json()