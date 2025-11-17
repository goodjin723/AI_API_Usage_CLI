"""
사용량 추적 로직
Usage API 데이터 처리 및 집계
"""
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta


def parse_usage_data(usage_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Usage API 응답 데이터 파싱
    
    공식 문서 형식:
    - time_series: [{"bucket": "...", "results": [...]}, ...]
    - summary: [{"endpoint_id": "...", "quantity": ..., "cost": ...}, ...]
    
    Returns:
        파싱된 데이터 구조
    """
    if not isinstance(usage_data, dict):
        return {
            "meta": {},
            "summary": {},
            "time_series": [],
            "auth_methods": {},
            "raw_items": []
        }
    
    meta = usage_data.get("_meta", {})
    
    # 최상위 time_series 추출 (공식 문서 형식)
    time_series = usage_data.get("time_series", [])
    if not isinstance(time_series, list):
        time_series = []
    
    # 최상위 summary 추출 (리스트 형식)
    summary = usage_data.get("summary", {})
    if not isinstance(summary, (dict, list)):
        summary = {}
    
    # auth_method 정보 추출 (summary 리스트에서)
    auth_methods = {}
    if isinstance(summary, list):
        for item in summary:
            if isinstance(item, dict) and "auth_method" in item:
                auth_method = item.get("auth_method")
                if isinstance(auth_method, str):
                    key_alias = auth_method
                elif isinstance(auth_method, dict):
                    key_alias = auth_method.get("key_alias", "Unknown")
                else:
                    key_alias = "Unknown"
                
                if key_alias not in auth_methods:
                    auth_methods[key_alias] = {
                        "requests": 0,
                        "quantity": 0,
                        "cost": 0.0
                    }
    
    return {
        "meta": meta,
        "summary": summary,
        "time_series": time_series,
        "auth_methods": auth_methods,
        "raw_items": []
    }


def parse_pricing_data(pricing_data: Dict[str, Any]) -> Dict[str, float]:
    """
    Pricing API 응답 데이터 파싱
    
    Returns:
        {endpoint_id: unit_price} 딕셔너리
    """
    pricing_map = {}
    
    # items, data, 또는 prices 필드 확인
    items = pricing_data.get("items", pricing_data.get("data", pricing_data.get("prices", [])))
    
    # items가 리스트가 아닌 경우 리스트로 변환
    if not isinstance(items, list):
        items = [items] if items else []
    
    for item in items:
        if isinstance(item, dict):
            endpoint_id = item.get("endpoint_id") or item.get("model")
            unit_price = item.get("unit_price") or item.get("price")
            if endpoint_id and unit_price is not None:
                pricing_map[endpoint_id] = float(unit_price)
    
    return pricing_map


def calculate_costs(
    usage_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    사용량 데이터에서 비용 계산 (Usage API의 unit_price 사용)
    
    Returns:
        계산된 데이터 구조
    """
    parsed = parse_usage_data(usage_data)
    
    # 모델별 집계
    model_stats = {}
    # 키별 집계
    auth_methods = parsed.get("auth_methods", {})
    total_requests = 0
    total_quantity = 0
    total_cost = 0.0
    
    # time_series 데이터 처리 (공식 문서 형식: bucket과 results 구조)
    for bucket_entry in parsed["time_series"]:
        if not isinstance(bucket_entry, dict):
            continue
        
        # results 배열에서 모델별 데이터 추출
        results = bucket_entry.get("results", [])
        if not isinstance(results, list):
            continue
        
        for result in results:
            if not isinstance(result, dict):
                continue
            
            endpoint_id = result.get("endpoint_id")
            if not endpoint_id:
                continue
            
            quantity = result.get("quantity", 0)
            unit_price = result.get("unit_price", 0.0)
            cost = result.get("cost", quantity * unit_price if unit_price else 0.0)
            
            # requests는 quantity와 동일하게 처리 (API에서 제공하지 않는 경우)
            requests = result.get("requests", quantity)
            
            # 모델별 집계
            if endpoint_id not in model_stats:
                model_stats[endpoint_id] = {
                    "requests": 0,
                    "quantity": 0,
                    "cost": 0.0,
                    "unit_price": unit_price
                }
            
            model_stats[endpoint_id]["requests"] += requests
            model_stats[endpoint_id]["quantity"] += quantity
            model_stats[endpoint_id]["cost"] += cost
            
            # 키별 집계
            auth_method = result.get("auth_method")
            if auth_method:
                if isinstance(auth_method, str):
                    key_alias = auth_method
                elif isinstance(auth_method, dict):
                    key_alias = auth_method.get("key_alias", "Unknown")
                else:
                    key_alias = "Unknown"
                
                if key_alias not in auth_methods:
                    auth_methods[key_alias] = {
                        "requests": 0,
                        "quantity": 0,
                        "cost": 0.0
                    }
                
                auth_methods[key_alias]["requests"] += requests
                auth_methods[key_alias]["quantity"] += quantity
                auth_methods[key_alias]["cost"] += cost
            
            total_requests += requests
            total_quantity += quantity
            total_cost += cost
    
    # summary 리스트 처리 (summary 형식)
    if isinstance(parsed["summary"], list):
        for item in parsed["summary"]:
            if not isinstance(item, dict):
                continue
            
            endpoint_id = item.get("endpoint_id")
            if not endpoint_id:
                continue
            
            quantity = item.get("quantity", item.get("units", 0))
            cost = item.get("cost", 0.0)
            requests = item.get("requests", item.get("count", quantity))
            
            # unit_price 추출
            unit_price = item.get("unit_price", 0.0)
            
            # 모델별 집계
            if endpoint_id not in model_stats:
                model_stats[endpoint_id] = {
                    "requests": 0,
                    "quantity": 0,
                    "cost": 0.0,
                    "unit_price": unit_price
                }
            
            # cost가 이미 계산되어 있으면 사용, 없으면 계산
            if cost == 0.0:
                cost = quantity * unit_price if unit_price else 0.0
            
            model_stats[endpoint_id]["requests"] += requests
            model_stats[endpoint_id]["quantity"] += quantity
            model_stats[endpoint_id]["cost"] += cost
            
            # 키별 집계
            auth_method = item.get("auth_method")
            if auth_method:
                if isinstance(auth_method, str):
                    key_alias = auth_method
                elif isinstance(auth_method, dict):
                    key_alias = auth_method.get("key_alias", "Unknown")
                else:
                    key_alias = "Unknown"
                
                if key_alias not in auth_methods:
                    auth_methods[key_alias] = {
                        "requests": 0,
                        "quantity": 0,
                        "cost": 0.0
                    }
                
                auth_methods[key_alias]["requests"] += requests
                auth_methods[key_alias]["quantity"] += quantity
                auth_methods[key_alias]["cost"] += cost
            
            total_requests += requests
            total_quantity += quantity
            total_cost += cost
    
    return {
        "total": {
            "requests": total_requests,
            "quantity": total_quantity,
            "cost": total_cost
        },
        "by_model": model_stats,
        "by_auth_method": auth_methods,
        "meta": parsed["meta"]
    }


def format_for_notion(
    usage_data: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Notion 저장용 데이터 변환
    auth_method별로 일별 상세 데이터를 그룹화
    
    Args:
        usage_data: Usage API 응답 데이터
    
    Returns:
        {auth_method: [일별 데이터 리스트]} 딕셔너리
    """
    parsed = parse_usage_data(usage_data)
    
    # timeframe 확인 (시/분 단위인지 체크)
    meta = parsed.get("meta", {})
    timeframe = meta.get("timeframe")
    
    # timeframe이 명시되지 않았을 때 기간 길이로 자동 판단
    if not timeframe:
        start_str = meta.get("start")
        end_str = meta.get("end")
        
        if start_str and end_str:
            try:
                # ISO8601 형식 파싱
                start_dt = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_dt = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                
                # 기간 길이 계산
                duration = end_dt - start_dt
                
                # API 자동 선택 규칙:
                # - 2시간 이내: minute
                # - 2일 이내: hour
                # - 그 이상: day 등
                if duration <= timedelta(hours=2):
                    timeframe = "minute"
                elif duration <= timedelta(days=2):
                    timeframe = "hour"
                else:
                    timeframe = "day"
            except (ValueError, AttributeError):
                # 파싱 실패 시 기본값으로 day 사용
                timeframe = "day"
        else:
            # start/end 정보가 없으면 기본값으로 day 사용
            timeframe = "day"
    
    include_time = timeframe in ["minute", "hour"]
    
    # auth_method별로 데이터 그룹화
    notion_data_by_auth: Dict[str, List[Dict[str, Any]]] = {}
    
    # time_series 데이터 처리 (bucket과 results 구조)
    for bucket_entry in parsed["time_series"]:
        if not isinstance(bucket_entry, dict):
            continue
        
        # bucket에서 날짜와 시간 추출
        bucket = bucket_entry.get("bucket", "")
        if isinstance(bucket, str):
            if "T" in bucket:
                date = bucket.split("T")[0]
                # 시/분 단위일 때만 시간 추출
                if include_time:
                    time_part = bucket.split("T")[1]
                    # 타임존 제거 (예: "14:30:00-05:00" -> "14:30:00")
                    if "+" in time_part:
                        time_str = time_part.split("+")[0]
                    elif "-" in time_part:
                        # 타임존이 -05:00 형식인 경우 (마지막 - 기준으로 분리)
                        # 예: "14:30:00-05:00" -> ["14:30:00", "05:00"]
                        parts = time_part.rsplit("-", 1)
                        if len(parts) == 2 and ":" in parts[1]:
                            # parts[1]이 타임존 형식 (예: "05:00")
                            time_str = parts[0]
                        else:
                            time_str = time_part.split("Z")[0] if "Z" in time_part else time_part
                    else:
                        time_str = time_part.split("Z")[0] if "Z" in time_part else time_part
                else:
                    time_str = None
            else:
                date = bucket
                time_str = None
        else:
            continue
        
        # results 배열에서 모델별 데이터 추출
        results = bucket_entry.get("results", [])
        if not isinstance(results, list):
            continue
        
        for result in results:
            if not isinstance(result, dict):
                continue
            
            endpoint_id = result.get("endpoint_id")
            if not endpoint_id:
                continue
            
            quantity = result.get("quantity", 0)
            unit_price = result.get("unit_price", 0.0)
            cost = result.get("cost", quantity * unit_price)
            requests = result.get("requests", quantity)
            
            # auth_method 추출
            auth_method = result.get("auth_method")
            if auth_method:
                if isinstance(auth_method, str):
                    key_alias = auth_method
                elif isinstance(auth_method, dict):
                    key_alias = auth_method.get("key_alias", "Unknown")
                else:
                    key_alias = "Unknown"
            else:
                key_alias = "Unknown"
            
            # auth_method별로 그룹화
            if key_alias not in notion_data_by_auth:
                notion_data_by_auth[key_alias] = []
            
            record = {
                "date": date,
                "model": endpoint_id,
                "requests": requests,
                "quantity": quantity,
                "cost": cost,
                "unit_price": unit_price,
                "auth_method": key_alias
            }
            
            # 시/분 단위일 때만 시간 정보 추가
            if time_str:
                record["time"] = time_str
            
            notion_data_by_auth[key_alias].append(record)
    
    return notion_data_by_auth


