"""
fal.ai 사용량 추적 CLI
"""
import argparse
import sys
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box
import api_client
import config
import date_utils
import formatter
import usage_tracker
import notion_integration

# Rich console 인스턴스
console = Console()


def parse_args() -> argparse.Namespace:
    """CLI 인자 파싱"""
    parser = argparse.ArgumentParser(
        description="fal.ai 사용량 추적 CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    # API 키
    parser.add_argument(
        "-api-key",
        type=str,
        default=None,
        help="fal.ai Admin API 키 (환경 변수 FAL_ADMIN_API_KEY도 지원)"
    )
    
    # 모델 목록
    parser.add_argument(
        "-models",
        type=str,
        default=None,
        help="추적할 모델 목록 (쉼표 구분, 예: fal-ai/imagen4/preview/ultra,fal-ai/nano-banana). "
    )
    
    # 날짜 범위 설정 (상호 배타적)
    date_group = parser.add_mutually_exclusive_group()
    date_group.add_argument(
        "-preset",
        type=str,
        choices=["today", "yesterday", "last-7-days", "last-30-days", "this-month"],
        default=None,
        help="빠른 날짜 범위 선택"
    )
    date_group.add_argument(
        "-start-date",
        type=str,
        default=None,
        help="시작 날짜 (YYYY-MM-DD 또는 ISO8601 형식)"
    )
    
    parser.add_argument(
        "-end-date",
        type=str,
        default=None,
        help="종료 날짜 (YYYY-MM-DD 또는 ISO8601 형식, 기본값: 현재)"
    )
    
    # 집계 옵션
    parser.add_argument(
        "-timeframe",
        type=str,
        choices=["minute", "hour", "day", "week", "month"],
        default="day",
        help="집계 단위 (기본값: day)"
    )
    
    parser.add_argument(
        "-timezone",
        type=str,
        default=None,
        help=f"타임존 (기본값: {config.get_timezone()})"
    )
    
    parser.add_argument(
        "-bound-to-timeframe",
        type=lambda x: x.lower() in ["true", "1", "yes"],
        default=True,
        help="timeframe 경계 정렬 활성화 (기본값: true)"
    )
    
    # Notion 옵션
    parser.add_argument(
        "-notion",
        action="store_true",
        help="Notion 데이터베이스에 저장"
    )
    
    parser.add_argument(
        "-notion-database-id",
        type=str,
        default=None,
        help="Notion 데이터베이스 ID (환경 변수 NOTION_DATABASE_ID도 지원)"
    )
    
    parser.add_argument(
        "-notion-api-key",
        type=str,
        default=None,
        help="Notion API 키 (환경 변수 NOTION_API_KEY도 지원)"
    )
    
    # 기타 옵션
    parser.add_argument(
        "-verbose",
        action="store_true",
        help="상세 로그 출력"
    )
    
    parser.add_argument(
        "-dry-run",
        action="store_true",
        help="실제 저장 없이 미리보기만"
    )
    
    parser.add_argument(
        "-update-existing",
        action="store_true",
        help="Notion에 중복 데이터가 있으면 업데이트 (기본값: 중복 시 스킵)"
    )
    
    return parser.parse_args()


def get_models_from_args(args: argparse.Namespace) -> List[str]:
    """
    모델 목록 가져오기 (CLI 옵션 또는 config.json)
    
    Returns:
        모델 ID 목록 (없으면 빈 리스트)
    """
    if args.models:
        # CLI에서 지정된 경우
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        if models:
            # config.json에 저장
            config.save_models(models)
            return models
        return []
    else:
        # config.json에서 가져오기
        return config.get_models()


def parse_date_range(args: argparse.Namespace) -> tuple[datetime, datetime]:
    """
    날짜 범위 파싱
    
    Returns:
        (시작 날짜, 종료 날짜) 튜플
    """
    tz = args.timezone or config.get_timezone()
    
    return date_utils.parse_date_range(
        preset=args.preset,
        start_date=args.start_date,
        end_date=args.end_date,
        tz=tz
    )


def show_main_menu() -> int:
    """메인 메뉴 표시"""
    console.print()

    # 메뉴 테이블 생성
    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("번호", style="bold cyan", width=4)
    table.add_column("메뉴", style="white")

    table.add_row("1", "모델 관리")
    table.add_row("2", "날짜 범위 설정")
    table.add_row("3", "API 키 설정")
    table.add_row("4", "Notion 설정 [dim](API 키, 데이터베이스)[/dim]")
    table.add_row("5", "Notion 저장 옵션 [dim](저장, 업데이트)[/dim]")
    table.add_row("6", "[bold green]조회 실행[/bold green]")
    table.add_row("7", "[dim]종료[/dim]")

    panel = Panel(
        table,
        title="[bold blue]🚀 fal.ai 사용량 추적 CLI[/bold blue]",
        border_style="blue",
        padding=(0, 1)
    )
    console.print(panel)

    while True:
        try:
            choice = Prompt.ask("\n[cyan]메뉴 선택[/cyan]", choices=["1", "2", "3", "4", "5", "6", "7"])
            return int(choice)
        except KeyboardInterrupt:
            console.print("\n[yellow]프로그램을 종료합니다.[/yellow]")
            sys.exit(0)
        except Exception:
            console.print("[red]올바른 숫자를 입력하세요.[/red]")


def show_model_menu() -> None:
    """모델 관리 메뉴"""
    while True:
        models = config.get_models()
        console.print()
        console.print("[bold cyan]📦 모델 관리[/bold cyan]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # 현재 모델 목록
        if models:
            status = f"[green]등록된 모델: {len(models)}개[/green]"
            console.print(status)
            console.print()

            model_table = Table(show_header=True, box=box.SIMPLE, border_style="green")
            model_table.add_column("번호", style="cyan", width=6)
            model_table.add_column("모델 ID", style="white")

            for i, model in enumerate(models, 1):
                model_table.add_row(str(i), model)

            console.print(model_table)
        else:
            console.print("[dim]등록된 모델이 없습니다.[/dim]")

        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")

        menu_table.add_row("1", "모델 추가")
        menu_table.add_row("2", "모델 삭제" if models else "[dim]모델 삭제[/dim]")
        menu_table.add_row("3", "뒤로 가기")

        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3"])
            if choice == "1":
                add_model()
            elif choice == "2":
                if models:
                    delete_model()
                else:
                    console.print("[yellow]삭제할 모델이 없습니다.[/yellow]")
            elif choice == "3":
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")


def add_model() -> None:
    """모델 추가"""
    console.print()
    console.print("[bold cyan]➕ 모델 추가[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")
    console.print()
    console.print("[dim]예: fal-ai/imagen4/preview/ultra[/dim]")

    model_id = Prompt.ask("[cyan]모델 ID[/cyan]").strip()

    if not model_id:
        console.print("[red]모델 ID를 입력해주세요.[/red]")
        return

    models = config.get_models()
    if model_id in models:
        console.print(f"[yellow]'{model_id}'는 이미 등록되어 있습니다.[/yellow]")
        return

    models.append(model_id)
    config.save_models(models)
    console.print(f"[green]✓ '{model_id}'가 추가되었습니다.[/green]")


def delete_model() -> None:
    """모델 삭제"""
    models = config.get_models()
    if not models:
        console.print("[yellow]삭제할 모델이 없습니다.[/yellow]")
        return

    console.print()
    console.print("[bold yellow]➖ 모델 삭제[/bold yellow]")
    console.print("[dim]" + "─" * 50 + "[/dim]")
    console.print()

    # 모델 목록 표시
    table = Table(show_header=True, box=box.SIMPLE, border_style="yellow")
    table.add_column("번호", style="yellow", width=6)
    table.add_column("모델 ID", style="white")

    for i, model in enumerate(models, 1):
        table.add_row(str(i), model)

    console.print(table)

    try:
        choice = Prompt.ask("\n[yellow]삭제할 모델 번호[/yellow]", choices=[str(i) for i in range(1, len(models) + 1)])
        deleted = models.pop(int(choice) - 1)
        config.save_models(models)
        console.print(f"[green]✓ '{deleted}'가 삭제되었습니다.[/green]")
    except Exception as e:
        console.print(f"[red]오류: {e}[/red]")


def show_date_range_menu(args: argparse.Namespace) -> Dict[str, Any]:
    """날짜 범위 설정 메뉴"""
    date_settings = {
        "preset": None,
        "start_date": None,
        "end_date": None
    }

    while True:
        console.print()
        console.print("[bold magenta]📅 날짜 범위 설정[/bold magenta]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # 현재 설정 및 실제 날짜 범위 표시
        try:
            start, end = parse_date_range(args)
            start_display = start.strftime("%Y-%m-%d %H:%M:%S")
            end_display = end.strftime("%Y-%m-%d %H:%M:%S")

            # 현재 설정 정보
            info_table = Table(show_header=False, box=None, padding=(0, 1))
            info_table.add_column("항목", style="cyan", width=12)
            info_table.add_column("값", style="white")

            if args.preset:
                preset_names = {
                    "today": "오늘",
                    "yesterday": "어제",
                    "last-7-days": "최근 7일",
                    "last-30-days": "최근 30일",
                    "this-month": "이번 달"
                }
                preset_name = preset_names.get(args.preset, args.preset)
                info_table.add_row("현재 설정", f"[green]{preset_name}[/green]")
            elif args.start_date:
                end_desc = args.end_date if args.end_date else "현재"
                info_table.add_row("현재 설정", f"[green]{args.start_date} ~ {end_desc}[/green]")
            else:
                info_table.add_row("현재 설정", "[dim]기본값[/dim]")

            info_table.add_row("실제 범위", f"[yellow]{start_display}[/yellow]\n[yellow]~ {end_display}[/yellow]")

            console.print(info_table)

        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")

        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")

        menu_table.add_row("1", "프리셋 선택 [dim](오늘, 어제, 최근 7일 등)[/dim]")
        menu_table.add_row("2", "시작/종료 날짜 직접 입력")
        menu_table.add_row("3", "뒤로 가기")

        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3"])
            if choice == "1":
                preset = select_preset()
                if preset:
                    date_settings["preset"] = preset
                    date_settings["start_date"] = None
                    date_settings["end_date"] = None
                    return date_settings
            elif choice == "2":
                start, end = input_custom_date_range()
                if start:
                    date_settings["preset"] = None
                    date_settings["start_date"] = start
                    date_settings["end_date"] = end
                    return date_settings
            elif choice == "3":
                return date_settings
        except KeyboardInterrupt:
            return date_settings
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")


def select_preset() -> Optional[str]:
    """프리셋 선택"""
    console.print()
    console.print("[bold magenta]📅 프리셋 선택[/bold magenta]")
    console.print("[dim]" + "─" * 50 + "[/dim]")
    console.print()

    table = Table(show_header=False, box=None, padding=(0, 2))
    table.add_column("번호", style="bold cyan", width=4)
    table.add_column("프리셋", style="white")

    table.add_row("1", "오늘 (today)")
    table.add_row("2", "어제 (yesterday)")
    table.add_row("3", "최근 7일 (last-7-days)")
    table.add_row("4", "최근 30일 (last-30-days)")
    table.add_row("5", "이번 달 (this-month)")
    table.add_row("6", "취소")

    console.print(table)

    presets = {
        "1": "today",
        "2": "yesterday",
        "3": "last-7-days",
        "4": "last-30-days",
        "5": "this-month"
    }

    try:
        choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3", "4", "5", "6"])
        if choice == "6":
            return None
        return presets.get(choice)
    except KeyboardInterrupt:
        return None
    except Exception:
        return None


def input_custom_date_range() -> tuple[Optional[str], Optional[str]]:
    """사용자 정의 날짜 범위 입력"""
    console.print()
    console.print("[bold magenta]📅 날짜 범위 직접 입력[/bold magenta]")
    console.print("[dim]" + "─" * 50 + "[/dim]")
    console.print()
    console.print("[dim]형식: YYYY-MM-DD[/dim]")

    try:
        start = Prompt.ask("[cyan]시작 날짜[/cyan]").strip()
        if not start:
            console.print("[red]시작 날짜를 입력해주세요.[/red]")
            return None, None

        end = Prompt.ask("[cyan]종료 날짜 [dim](엔터 시 현재 날짜)[/dim][/cyan]", default="").strip()
        return start, end if end else None
    except KeyboardInterrupt:
        return None, None
    except Exception:
        return None, None


def show_api_key_menu() -> None:
    """API 키 설정 메뉴"""
    while True:
        console.print()
        console.print("[bold green]🔑 API 키 설정[/bold green]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        api_key = config.get_api_key()
        if api_key:
            # 마스킹 처리
            masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
            status = f"[green]{masked_key}[/green]"
        else:
            status = "[dim]등록된 API 키 없음[/dim]"

        # 현재 설정 및 메뉴
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=12)
        info_table.add_column("값", style="white")
        info_table.add_row("현재 API 키", status)

        console.print(info_table)
        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")
        menu_table.add_row("1", "API 키 입력/변경")
        menu_table.add_row("2", "뒤로 가기")

        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2"])
            if choice == "1":
                console.print()
                api_key = Prompt.ask("[cyan]fal.ai Admin API 키[/cyan]").strip()
                if api_key:
                    config.save_api_key(api_key)
                    console.print("[green]✓ API 키가 저장되었습니다.[/green]")
                else:
                    console.print("[red]API 키를 입력해주세요.[/red]")
            elif choice == "2":
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")


def show_notion_save_menu(args: argparse.Namespace) -> None:
    """Notion 저장 옵션 메뉴"""
    while True:
        console.print()
        console.print("[bold yellow]💾 Notion 저장 옵션[/bold yellow]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # 현재 모드 결정
        if args.notion:
            save_status = "[green]●[/green] 활성화"
            mode_marker = ["  ", "[green]●[/green]"]
        else:
            save_status = "[dim]○[/dim] 비활성화"
            mode_marker = ["[yellow]●[/yellow]", "  "]

        update_status = "[green]업데이트[/green]" if args.update_existing else "[dim]스킵[/dim]"

        # 현재 설정
        status_table = Table(show_header=False, box=None, padding=(0, 1))
        status_table.add_column("항목", style="cyan", width=16)
        status_table.add_column("상태", style="white")

        status_table.add_row("저장 모드", save_status)
        status_table.add_row("중복 데이터 처리", update_status)

        console.print(status_table)
        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("", width=3)
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")

        menu_table.add_row(mode_marker[0], "1", "비활성화 [dim](Notion에 저장하지 않음)[/dim]")
        menu_table.add_row(mode_marker[1], "2", "활성화 [dim](Notion에 저장)[/dim]")
        menu_table.add_row("", "", "")
        menu_table.add_row("", "3", f"중복 데이터 업데이트 ON/OFF [dim](현재: {update_status})[/dim]")
        menu_table.add_row("", "4", "뒤로 가기")

        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3", "4"])
            if choice == "1":
                args.notion = False
                args.dry_run = False
                console.print("[green]✓ Notion 저장이 비활성화되었습니다.[/green]")
            elif choice == "2":
                args.notion = True
                args.dry_run = False
                console.print("[green]✓ Notion 저장이 활성화되었습니다.[/green]")
            elif choice == "3":
                args.update_existing = not args.update_existing
                status = "활성화" if args.update_existing else "비활성화"
                console.print(f"[green]✓ 중복 데이터 업데이트가 {status}되었습니다.[/green]")
            elif choice == "4":
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")


def show_notion_menu() -> None:
    """Notion 설정 메뉴"""
    while True:
        console.print()
        console.print("[bold blue]📝 Notion 설정[/bold blue]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # Notion API 키 확인
        notion_api_key = config.get_notion_api_key()
        if notion_api_key:
            masked_key = notion_api_key[:8] + "..." + notion_api_key[-4:] if len(notion_api_key) > 12 else "***"
            api_key_status = f"[green]{masked_key}[/green]"
        else:
            api_key_status = "[dim]등록된 API 키 없음[/dim]"

        # 등록된 데이터베이스 목록
        databases = config.get_all_notion_databases()

        # 현재 설정 정보
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=16)
        info_table.add_column("값", style="white")
        info_table.add_row("Notion API 키", api_key_status)

        if databases:
            db_list = "\n".join([f"[white]{auth}: {db_id[:8]}...{db_id[-4:]}[/white]"
                                 for auth, db_id in databases.items()])
            info_table.add_row("데이터베이스", db_list)
        else:
            info_table.add_row("데이터베이스", "[dim]등록된 데이터베이스 없음[/dim]")

        console.print(info_table)
        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")
        menu_table.add_row("1", "Notion API 키 입력/변경")
        menu_table.add_row("2", "데이터베이스 ID 추가/수정")
        menu_table.add_row("3", "데이터베이스 ID 삭제" if databases else "[dim]데이터베이스 ID 삭제[/dim]")
        menu_table.add_row("4", "뒤로 가기")

        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3", "4"])
            if choice == "1":
                console.print()
                notion_api_key = Prompt.ask("[cyan]Notion API 키[/cyan]").strip()
                if notion_api_key:
                    try:
                        config.save_notion_api_key(notion_api_key)
                        console.print("[green]✓ Notion API 키가 저장되었습니다.[/green]")
                    except Exception as e:
                        console.print(f"[red]Notion API 키 저장 실패: {e}[/red]")
                else:
                    console.print("[red]Notion API 키를 입력해주세요.[/red]")
            elif choice == "2":
                console.print()
                auth_method = Prompt.ask("[cyan]키 별칭 (auth_method)[/cyan]").strip()
                if not auth_method:
                    console.print("[red]키 별칭을 입력해주세요.[/red]")
                    continue

                database_id = Prompt.ask("[cyan]Notion 데이터베이스 ID[/cyan]").strip()
                if database_id:
                    config.save_notion_database_id(auth_method, database_id)
                    console.print(f"[green]✓ '{auth_method}'의 데이터베이스 ID가 저장되었습니다.[/green]")
                else:
                    console.print("[red]데이터베이스 ID를 입력해주세요.[/red]")
            elif choice == "3":
                databases = config.get_all_notion_databases()
                if not databases:
                    console.print("[yellow]삭제할 데이터베이스가 없습니다.[/yellow]")
                    continue

                console.print()
                console.print("[cyan]삭제할 데이터베이스의 키 별칭:[/cyan]")
                for auth_method in databases.keys():
                    console.print(f"  - [white]{auth_method}[/white]")

                console.print()
                auth_method = Prompt.ask("[yellow]키 별칭[/yellow]",
                                        choices=list(databases.keys()))

                # config에서 제거
                config_data = config.get_config()
                if "notion_databases" in config_data:
                    del config_data["notion_databases"][auth_method]
                    config.save_config(config_data)
                console.print(f"[green]✓ '{auth_method}'의 데이터베이스 ID가 삭제되었습니다.[/green]")
            elif choice == "4":
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")


def validate_and_execute_query(args: argparse.Namespace) -> None:
    """필수 값 검증 후 조회 실행"""
    # API 키 확인
    api_key = config.get_api_key(args.api_key)
    if not api_key:
        console.print("\n[red]API 키가 설정되지 않았습니다.[/red]")
        console.print("[yellow]메뉴에서 '3. API 키 설정'을 선택하여 API 키를 설정해주세요.[/yellow]")
        return

    # 모델 목록 확인
    models = get_models_from_args(args)
    if not models:
        console.print("\n[red]모델 목록이 비어있습니다.[/red]")
        console.print("[yellow]메뉴에서 '1. 모델 관리'를 선택하여 모델을 추가해주세요.[/yellow]")
        return

    # 날짜 범위 확인
    try:
        start, end = parse_date_range(args)
    except Exception as e:
        console.print(f"\n[red]날짜 범위 설정 오류: {e}[/red]")
        console.print("[yellow]메뉴에서 '2. 날짜 범위 설정'을 선택하여 날짜를 설정해주세요.[/yellow]")
        return

    # 조회 실행
    execute_query(args, api_key, models, start, end)


def save_to_notion(
    usage_data: Dict[str, Any],
    cli_notion_api_key: Optional[str],
    dry_run: bool,
    verbose: bool,
    update_existing: bool = False
) -> None:
    """Notion에 데이터 저장"""
    try:
        # Notion API 키 확인
        notion_api_key = config.get_notion_api_key(cli_notion_api_key)
        if not notion_api_key:
            console.print("\n[red]Notion API 키가 설정되지 않았습니다.[/red]")
            console.print("[yellow]환경 변수 NOTION_API_KEY를 설정하거나 -notion-api-key 옵션을 사용하세요.[/yellow]")
            return

        # Notion 클라이언트 생성
        notion = notion_integration.NotionClient(notion_api_key)

        # 사용량 데이터를 Notion 형식으로 변환
        notion_data_by_auth = usage_tracker.format_for_notion(usage_data)

        if not notion_data_by_auth:
            console.print("\n[yellow]저장할 Notion 데이터가 없습니다.[/yellow]")
            return

        if dry_run:
            console.print("\n[yellow][DRY-RUN] Notion 저장 모드 (실제 저장 안 함)[/yellow]")
            for auth_method, records in notion_data_by_auth.items():
                console.print(f"  - {auth_method}: {len(records)}개 레코드")
            return

        # auth_method별로 데이터 저장
        total_created = 0
        total_updated = 0
        total_skipped = 0

        if verbose:
            console.print(f"\n[dim][DEBUG] 변환된 데이터: {len(notion_data_by_auth)}개 auth_method[/dim]")
            for auth_method, records in notion_data_by_auth.items():
                console.print(f"  - {auth_method}: {len(records)}개 레코드")

        for auth_method, records in notion_data_by_auth.items():
            if verbose:
                console.print(f"\n[dim][DEBUG] 처리 중인 auth_method: '{auth_method}' ({len(records)}개 레코드)[/dim]")

            # 해당 auth_method의 데이터베이스 ID 가져오기
            database_id = config.get_notion_database_id(auth_method)

            # 데이터베이스 ID가 없으면 등록된 모든 데이터베이스 확인
            if not database_id:
                all_databases = config.get_all_notion_databases()

                # 등록된 데이터베이스가 하나만 있으면 자동으로 사용
                if len(all_databases) == 1:
                    database_id = list(all_databases.values())[0]
                    if verbose:
                        console.print(f"[yellow]'{auth_method}'의 데이터베이스 ID가 없어서 유일한 데이터베이스를 사용합니다.[/yellow]")
                else:
                    if verbose:
                        console.print(f"[yellow][WARNING] '{auth_method}'의 Notion 데이터베이스 ID가 설정되지 않았습니다.[/yellow]")
                        console.print(f"[dim]          등록된 데이터베이스 키: {list(all_databases.keys())}[/dim]")
                        console.print(f"[dim]          {len(records)}개 레코드가 스킵되었습니다.[/dim]")
                        console.print(f"\n[cyan]해결 방법:[/cyan]")
                        console.print(f"[dim]          1. 인터랙티브 메뉴에서 '4. Notion 설정' > '2. 데이터베이스 ID 추가/수정' 선택[/dim]")
                        console.print(f"[dim]          2. 키 별칭에 '{auth_method}' 입력[/dim]")
                        console.print(f"[dim]          3. 해당 데이터베이스 ID 입력[/dim]")
                    total_skipped += len(records)
                    continue

            # 데이터베이스 존재 여부 확인
            if verbose:
                console.print(f"[dim][DEBUG] 데이터베이스 ID 확인 중: {database_id}[/dim]")
            if not notion.check_database_exists(database_id, verbose=verbose):
                console.print(f"\n[red]'{auth_method}'의 데이터베이스(ID: {database_id})를 찾을 수 없습니다.[/red]")
                total_skipped += len(records)
                continue

            # 데이터 저장
            if verbose:
                console.print(f"\n[cyan]'{auth_method}' 데이터베이스에 저장 중... ({len(records)}개 레코드)[/cyan]")
            if update_existing:
                console.print(f"[yellow]중복 데이터 발견 시 업데이트 모드[/yellow]")
            else:
                console.print(f"[yellow]중복 데이터 발견 시 스킵 모드 (중복 방지)[/yellow]")

            stats = notion.save_usage_data(database_id, records, update_existing=update_existing, verbose=verbose)
            total_created += stats["created"]
            total_updated += stats["updated"]
            total_skipped += stats["skipped"]

            if verbose:
                console.print(f"[green]생성: {stats['created']}, 업데이트: {stats['updated']}, 스킵: {stats['skipped']}[/green]")

        console.print(f"\n[green]✓ Notion 저장 완료 (생성: {total_created}, 업데이트: {total_updated}, 스킵: {total_skipped})[/green]")

    except Exception as e:
        console.print(f"\n[red]Notion 저장 중 오류 발생: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()


def execute_query(
    args: argparse.Namespace,
    api_key: str,
    models: List[str],
    start: datetime,
    end: datetime
) -> None:
    """실제 조회 실행"""
    try:
        console.print()

        # 1단계: 준비
        console.print("[cyan]⏳ API 호출 준비 중...[/cyan]")

        if args.verbose:
            console.print(f"[dim]   모델 목록: {', '.join(models)}[/dim]")
            # 조회 기간을 일반 날짜 형식으로 출력
            start_display = start.strftime("%Y-%m-%d %H:%M:%S")
            end_display = end.strftime("%Y-%m-%d %H:%M:%S")
            console.print(f"[dim]   조회 기간: {start_display} ~ {end_display}[/dim]")

        timezone = args.timezone or config.get_timezone()

        # API 클라이언트 생성
        client = api_client.FalAPIClient(api_key)

        # 2단계: Usage API 호출
        console.print("[cyan]⏳ 사용량 데이터 조회 중...[/cyan]")

        usage_data = client.get_usage(
            endpoint_ids=models,
            start=start,
            end=end,
            timeframe=args.timeframe,
            timezone=timezone,
            bound_to_timeframe=args.bound_to_timeframe,
            include_notion=args.notion
        )

        console.print("[green]✓ 데이터 조회 완료[/green]")

        # 3단계: 데이터 처리 및 출력
        console.print("[cyan]⏳ 데이터 처리 중...[/cyan]")

        # 테이블 형식 출력
        formatter.format_for_display(usage_data)

        # 4단계: Notion 저장
        if args.notion:
            console.print()
            console.print("[cyan]⏳ Notion에 저장 중...[/cyan]")
            save_to_notion(usage_data, args.notion_api_key, args.dry_run, args.verbose, args.update_existing)

        console.print()
        console.print("[green]✓ 모든 작업 완료[/green]")

    except Exception as e:
        console.print(f"\n[red]❌ 조회 중 오류 발생: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()


def main():
    """메인 실행 함수"""
    try:
        # 인자 파싱
        args = parse_args()

        # CLI 인자가 모두 비어있으면 인터랙티브 모드
        # 기본값이 설정된 인자는 제외하고, 실제로 사용자가 명시한 인자만 체크
        has_cli_args = any([
            args.api_key,
            args.models,
            args.preset,
            args.start_date,
            args.end_date,
            args.timezone,  # 기본값이 None이므로 그대로 체크
            args.notion,
            args.verbose,
            args.dry_run
            # args.timeframe과 args.bound_to_timeframe은 기본값이 있으므로 제외
        ])

        if not has_cli_args:
            # 인터랙티브 모드
            interactive_mode(args)
        else:
            # CLI 모드 (기존 동작)
            cli_mode(args)

    except KeyboardInterrupt:
        console.print("\n\n[yellow]프로그램을 종료합니다.[/yellow]")
        sys.exit(0)
    except ValueError as e:
        console.print(f"[red]{e}[/red]", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]예상치 못한 오류: {e}[/red]", file=sys.stderr)
        if 'args' in locals() and args.verbose:
            import traceback
            traceback.print_exc()
        sys.exit(1)


def interactive_mode(args: argparse.Namespace) -> None:
    """인터랙티브 모드"""
    date_settings = {}

    while True:
        choice = show_main_menu()

        if choice == 1:
            show_model_menu()
        elif choice == 2:
            date_settings = show_date_range_menu(args)
            # args에 반영
            if date_settings.get("preset"):
                args.preset = date_settings["preset"]
                args.start_date = None
                args.end_date = None
            elif date_settings.get("start_date"):
                args.preset = None
                args.start_date = date_settings["start_date"]
                args.end_date = date_settings.get("end_date")
        elif choice == 3:
            show_api_key_menu()
        elif choice == 4:
            show_notion_menu()
        elif choice == 5:
            show_notion_save_menu(args)
        elif choice == 6:
            validate_and_execute_query(args)
            Prompt.ask("\n[dim]계속하려면 엔터를 누르세요[/dim]", default="")
        elif choice == 7:
            console.print("\n[yellow]프로그램을 종료합니다.[/yellow]")
            break


def cli_mode(args: argparse.Namespace) -> None:
    """CLI 모드 (기존 동작)"""
    # API 키 가져오기
    api_key = config.get_api_key(args.api_key)
    if not api_key:
        raise ValueError(
            "fal.ai Admin API 키가 필요합니다. "
            "환경 변수 FAL_ADMIN_API_KEY를 설정하거나 -api-key 옵션을 사용하세요."
        )

    # 모델 목록 가져오기
    models = get_models_from_args(args)
    if not models:
        raise ValueError(
            "모델 목록이 지정되지 않았습니다. "
            "-models 옵션으로 모델 목록을 지정해주세요. "
            "예: -models fal-ai/imagen4/preview/ultra,fal-ai/nano-banana"
        )

    if args.verbose:
        console.print(f"[dim]모델 목록: {', '.join(models)}[/dim]")
        if args.models:
            console.print(f"[dim]모델 목록이 config.json에 저장되었습니다.[/dim]")

    # 날짜 범위 파싱
    start, end = parse_date_range(args)

    if args.verbose:
        # 조회 기간을 일반 날짜 형식으로 출력
        start_display = start.strftime("%Y-%m-%d %H:%M:%S")
        end_display = end.strftime("%Y-%m-%d %H:%M:%S")
        console.print(f"[dim]조회 기간: {start_display} ~ {end_display}[/dim]")

    # 조회 실행
    execute_query(args, api_key, models, start, end)


if __name__ == "__main__":
    main()

