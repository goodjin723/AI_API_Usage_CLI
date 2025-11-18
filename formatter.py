"""
데이터 출력 및 포맷팅
CLI 테이블 형식 출력
"""
from typing import Dict, Any
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
import usage_tracker


console = Console()


def format_currency(amount: float) -> str:
    """통화 형식으로 포맷팅"""
    return f"${amount:.4f}"


def format_number(num: float) -> str:
    """숫자 포맷팅 (천 단위 구분)"""
    return f"{num:,.0f}"


def print_period_info(meta: Dict[str, Any]):
    """조회 기간 정보 출력"""
    start_str = meta.get("start", "")
    end_str = meta.get("end", "")
    timezone = meta.get("timezone", "")
    timeframe = meta.get("timeframe")

    # ISO8601 형식을 일반 날짜 형식으로 변환
    try:
        if start_str:
            # Z를 +00:00으로 변환 (fromisoformat 호환성)
            # 이미 타임존 정보가 포함된 경우 그대로 사용
            if start_str.endswith('Z'):
                start_str_parsed = start_str.replace('Z', '+00:00')
            else:
                start_str_parsed = start_str
            start_dt = datetime.fromisoformat(start_str_parsed)
            # 타임존 정보가 포함된 datetime 객체의 값 그대로 출력
            # (이미 사용자 타임존으로 변환된 값이므로 그대로 출력)
            start_display = start_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            start_display = start_str
    except (ValueError, AttributeError):
        start_display = start_str

    try:
        if end_str:
            # Z를 +00:00으로 변환 (fromisoformat 호환성)
            # 이미 타임존 정보가 포함된 경우 그대로 사용
            if end_str.endswith('Z'):
                end_str_parsed = end_str.replace('Z', '+00:00')
            else:
                end_str_parsed = end_str
            end_dt = datetime.fromisoformat(end_str_parsed)
            # 타임존 정보가 포함된 datetime 객체의 값 그대로 출력
            # (이미 사용자 타임존으로 변환된 값이므로 그대로 출력)
            end_display = end_dt.strftime("%Y-%m-%d %H:%M:%S")
        else:
            end_display = end_str
    except (ValueError, AttributeError):
        end_display = end_str

    # Panel 안에 한 줄로 표시
    info_text = f"조회 기간: {start_display} ~ {end_display}"
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
    usage_data: Dict[str, Any]
) -> None:
    """
    CLI 화면에 테이블 형식으로 출력
    
    Args:
        usage_data: Usage API 응답 데이터
    """
    # 비용 계산 (Usage API의 unit_price 사용)
    calculated_data = usage_tracker.calculate_costs(usage_data)
    
    # 출력
    console.print()
    print_period_info(calculated_data["meta"])
    console.print()
    
    print_summary_table(calculated_data)
    print_model_table(calculated_data)
    print_auth_method_table(calculated_data)

