"""
사용량 추적 로직
Usage API 데이터 처리 및 집계
"""
from typing import Dict, Any, List, Optional
from datetime import datetime


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
    usage_data: Dict[str, Any],
    pricing_map: Dict[str, float]
) -> Dict[str, Any]:
    """
    사용량 데이터와 가격 정보를 결합하여 비용 계산
    
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
            unit_price = result.get("unit_price") or pricing_map.get(endpoint_id, 0.0)
            cost = result.get("cost", quantity * unit_price)
            
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
            
            # 모델별 집계
            if endpoint_id not in model_stats:
                model_stats[endpoint_id] = {
                    "requests": 0,
                    "quantity": 0,
                    "cost": 0.0,
                    "unit_price": pricing_map.get(endpoint_id, item.get("unit_price", 0.0))
                }
            
            # cost가 이미 계산되어 있으면 사용, 없으면 계산
            if cost == 0.0:
                unit_price = pricing_map.get(endpoint_id, item.get("unit_price", 0.0))
                cost = quantity * unit_price
            
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
    usage_data: Dict[str, Any],
    pricing_data: Dict[str, Any]
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Notion 저장용 데이터 변환
    auth_method별로 일별 상세 데이터를 그룹화
    
    Args:
        usage_data: Usage API 응답 데이터
        pricing_data: Pricing API 응답 데이터
    
    Returns:
        {auth_method: [일별 데이터 리스트]} 딕셔너리
    """
    pricing_map = parse_pricing_data(pricing_data)
    parsed = parse_usage_data(usage_data)
    
    # auth_method별로 데이터 그룹화
    notion_data_by_auth: Dict[str, List[Dict[str, Any]]] = {}
    
    # time_series 데이터 처리 (bucket과 results 구조)
    for bucket_entry in parsed["time_series"]:
        if not isinstance(bucket_entry, dict):
            continue
        
        # bucket에서 날짜 추출
        bucket = bucket_entry.get("bucket", "")
        if isinstance(bucket, str):
            # ISO8601 형식에서 날짜만 추출
            if "T" in bucket:
                date = bucket.split("T")[0]
            else:
                date = bucket
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
            unit_price = result.get("unit_price") or pricing_map.get(endpoint_id, 0.0)
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
            
            notion_data_by_auth[key_alias].append({
                "date": date,
                "model": endpoint_id,
                "requests": requests,
                "quantity": quantity,
                "cost": cost,
                "unit_price": unit_price,
                "auth_method": key_alias
            })
    
    return notion_data_by_auth

