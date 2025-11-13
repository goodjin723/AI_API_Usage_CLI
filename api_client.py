"""
fal.ai API 클라이언트
Usage API 호출 및 페이지네이션 처리
"""
import requests  # type: ignore
from typing import Optional, List, Dict, Any
from datetime import datetime
import date_utils
import config


BASE_URL = "https://api.fal.ai/v1/models"
USAGE_ENDPOINT = f"{BASE_URL}/usage"


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
            
            # API 호출
            response = requests.get(USAGE_ENDPOINT, headers=self.headers, params=params)
            
            # 에러 처리
            if response.status_code != 200:
                error_msg = f"API 호출 실패: {response.status_code}"
                try:
                    error_data = response.json()
                    if "detail" in error_data:
                        error_msg += f" - {error_data['detail']}"
                except:
                    error_msg += f" - {response.text}"
                raise requests.exceptions.HTTPError(error_msg)
            
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
                cursor = data.get("cursor")
                has_more = data.get("has_more", False)
                
                # has_more가 null이면 더 이상 없음
                if has_more is None:
                    has_more = False
            else:
                # 리스트 형식인 경우
                all_data.extend(data)
                has_more = False
            
            # cursor가 없으면 종료
            if not cursor:
                has_more = False
        
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
        
        # 메타데이터 추가/업데이트
        if "_meta" not in result:
            result["_meta"] = {}
        result["_meta"].update({
            "start": start_str,
            "end": end_str,
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

