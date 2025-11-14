"""
데이터 출력 및 포맷팅
테이블 형식 출력 및 JSON 변환
"""
from typing import Dict, Any, List, Optional
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text
from datetime import datetime
import json


console = Console()


def format_currency(amount: float) -> str:
    """통화 형식으로 포맷팅"""
    return f"${amount:.4f}"


def format_number(num: float) -> str:
    """숫자 포맷팅 (천 단위 구분)"""
    return f"{num:,.0f}"


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


def parse_pricing_data(pricing_data: Dict[str, Any]) -> Dict[str, str]:
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


def print_period_info(meta: Dict[str, Any]):
    """조회 기간 정보 출력"""
    start = meta.get("start", "")
    end = meta.get("end", "")
    timezone = meta.get("timezone", "")
    timeframe = meta.get("timeframe")
    
    info_text = f"조회 기간: {start} ~ {end}"
    if timezone:
        info_text += f" | 타임존: {timezone}"
    if timeframe:
        info_text += f" | 집계 단위: {timeframe}"
    
    console.print(Panel(info_text, title="[bold blue]조회 정보[/bold blue]", border_style="blue"))


def print_summary_table(calculated_data: Dict[str, Any]):
    """전체 사용량 요약 테이블 출력"""
    total = calculated_data["total"]
    
    table = Table(title="[bold green]전체 사용량 요약[/bold green]", show_header=True, header_style="bold magenta")
    table.add_column("항목", style="cyan", no_wrap=True)
    table.add_column("값", style="green", justify="right")
    
    table.add_row("총 요청 수", format_number(total["requests"]))
    table.add_row("총 사용량", format_number(total["quantity"]))
    table.add_row("총 비용", format_currency(total["cost"]))
    
    console.print(table)
    console.print()


def print_model_table(calculated_data: Dict[str, Any]):
    """모델별 상세 사용량 테이블 출력"""
    by_model = calculated_data["by_model"]
    
    if not by_model:
        console.print("[yellow]모델별 데이터가 없습니다.[/yellow]")
        return
    
    table = Table(title="[bold green]모델별 상세 사용량[/bold green]", show_header=True, header_style="bold magenta")
    table.add_column("모델", style="cyan", no_wrap=False)
    table.add_column("요청 수", style="yellow", justify="right")
    table.add_column("사용량", style="yellow", justify="right")
    table.add_column("단가", style="blue", justify="right")
    table.add_column("비용", style="green", justify="right")
    
    # 비용 순으로 정렬
    sorted_models = sorted(
        by_model.items(),
        key=lambda x: x[1]["cost"],
        reverse=True
    )
    
    for endpoint_id, stats in sorted_models:
        table.add_row(
            endpoint_id,
            format_number(stats["requests"]),
            format_number(stats["quantity"]),
            format_currency(stats["unit_price"]),
            format_currency(stats["cost"])
        )
    
    console.print(table)
    console.print()


def print_auth_method_table(calculated_data: Dict[str, Any]):
    """사용자 키별 사용량 테이블 출력"""
    auth_methods = calculated_data.get("by_auth_method", {})
    
    if not auth_methods:
        # auth_method 정보가 없으면 스킵
        return
    
    table = Table(title="[bold green]사용자 키별 사용량[/bold green]", show_header=True, header_style="bold magenta")
    table.add_column("키 별칭", style="cyan", no_wrap=True)
    table.add_column("요청 수", style="yellow", justify="right")
    table.add_column("사용량", style="yellow", justify="right")
    table.add_column("비용", style="green", justify="right")
    
    for key_alias, stats in sorted(auth_methods.items(), key=lambda x: x[1]["cost"], reverse=True):
        table.add_row(
            key_alias,
            format_number(stats["requests"]),
            format_number(stats["quantity"]),
            format_currency(stats["cost"])
        )
    
    console.print(table)
    console.print()


def format_for_display(
    usage_data: Dict[str, Any],
    pricing_data: Dict[str, Any]
) -> None:
    """
    CLI 화면에 테이블 형식으로 출력
    
    Args:
        usage_data: Usage API 응답 데이터
        pricing_data: Pricing API 응답 데이터
    """
    # 가격 정보 파싱
    pricing_map = parse_pricing_data(pricing_data)
    
    # 비용 계산
    calculated_data = calculate_costs(usage_data, pricing_map)
    
    # 출력
    console.print()
    print_period_info(calculated_data["meta"])
    console.print()
    
    print_summary_table(calculated_data)
    print_model_table(calculated_data)
    print_auth_method_table(calculated_data)


def format_for_notion(
    usage_data: Dict[str, Any],
    pricing_data: Dict[str, Any]
) -> List[Dict[str, Any]]:
    """
    Notion 저장용 JSON 형식으로 변환
    
    Args:
        usage_data: Usage API 응답 데이터
        pricing_data: Pricing API 응답 데이터
    
    Returns:
        Notion 데이터베이스에 저장할 데이터 리스트
    """
    pricing_map = parse_pricing_data(pricing_data)
    parsed = parse_usage_data(usage_data)
    
    notion_records = []
    
    # time_series 데이터를 Notion 형식으로 변환
    for entry in parsed["time_series"]:
        endpoint_id = entry.get("endpoint_id") or entry.get("model")
        date = entry.get("date") or entry.get("timestamp")
        requests = entry.get("requests", entry.get("count", 0))
        quantity = entry.get("quantity", entry.get("units", requests))
        
        unit_price = pricing_map.get(endpoint_id, 0.0)
        cost = quantity * unit_price
        
        # 날짜 형식 정규화
        if isinstance(date, str):
            # ISO8601 형식에서 날짜만 추출
            if "T" in date:
                date = date.split("T")[0]
        elif isinstance(date, datetime):
            date = date.strftime("%Y-%m-%d")
        
        notion_records.append({
            "date": date,
            "model": endpoint_id,
            "requests": requests,
            "quantity": quantity,
            "cost": cost,
            "unit_price": unit_price
        })
    
    return notion_records


def format_to_json(
    usage_data: Dict[str, Any],
    pricing_data: Dict[str, Any]
) -> Dict[str, Any]:
    """
    전체 데이터를 JSON 형식으로 변환 (디버깅/저장용)
    
    Returns:
        구조화된 JSON 데이터
    """
    pricing_map = parse_pricing_data(pricing_data)
    calculated_data = calculate_costs(usage_data, pricing_map)
    parsed = parse_usage_data(usage_data)
    meta = calculated_data["meta"]
    
    # 모델별 상세 데이터
    models_data = []
    for endpoint_id, stats in calculated_data["by_model"].items():
        models_data.append({
            "model": endpoint_id,
            "requests": stats["requests"],
            "quantity": stats["quantity"],
            "cost": stats["cost"],
            "unit_price": stats["unit_price"]
        })
    
    return {
        "period": {
            "start": meta.get("start"),
            "end": meta.get("end"),
            "timezone": meta.get("timezone"),
            "timeframe": meta.get("timeframe")
        },
        "summary": {
            "total_requests": calculated_data["total"]["requests"],
            "total_quantity": calculated_data["total"]["quantity"],
            "total_cost": calculated_data["total"]["cost"]
        },
        "models": models_data,
        "pricing": pricing_map
    }

