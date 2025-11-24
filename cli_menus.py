"""
CLI 인터랙티브 메뉴 모듈
사용자 인터페이스 및 메뉴 관리
"""
import sys
import argparse
from typing import Optional, Dict, Any
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.prompt import Prompt
from rich import box
import config
import date_utils


# Rich console 인스턴스
console = Console()


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
    table.add_row("6", "[bold green]조회 실행 (fal.ai 사용량)[/bold green]")
    table.add_row("7", "[bold yellow]Invoice 관리 (Gmail)[/bold yellow]")
    table.add_row("8", "[dim]종료[/dim]")

    panel = Panel(
        table,
        title="[bold blue]🚀 fal.ai 사용량 추적 CLI[/bold blue]",
        border_style="blue",
        padding=(0, 1)
    )
    console.print(panel)

    while True:
        try:
            choice = Prompt.ask("\n[cyan]메뉴 선택[/cyan]", choices=["1", "2", "3", "4", "5", "6", "7", "8"])
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
            start, end = date_utils.parse_date_range(
                preset=args.preset,
                start_date=args.start_date,
                end_date=args.end_date,
                tz=args.timezone or config.get_timezone()
            )
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

        # fal.ai API 키 확인
        fal_api_key = config.get_api_key()
        if fal_api_key:
            masked_fal = fal_api_key[:8] + "..." + fal_api_key[-4:] if len(fal_api_key) > 12 else "***"
            fal_status = f"[green]{masked_fal}[/green]"
        else:
            fal_status = "[dim]등록된 API 키 없음[/dim]"

        # OpenAI API 키 확인
        openai_api_key = config.get_openai_api_key()
        if openai_api_key:
            masked_openai = openai_api_key[:8] + "..." + openai_api_key[-4:] if len(openai_api_key) > 12 else "***"
            openai_status = f"[green]{masked_openai}[/green]"
        else:
            openai_status = "[dim]등록된 API 키 없음[/dim]"

        # 현재 설정 표시
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=16)
        info_table.add_column("값", style="white")
        info_table.add_row("fal.ai API 키", fal_status)
        info_table.add_row("OpenAI API 키", openai_status)

        console.print(info_table)
        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")
        menu_table.add_row("1", "fal.ai API 키 입력/변경")
        menu_table.add_row("2", "OpenAI API 키 입력/변경")
        menu_table.add_row("3", "뒤로 가기")

        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3"])
            if choice == "1":
                console.print()
                api_key = Prompt.ask("[cyan]fal.ai Admin API 키[/cyan]").strip()
                if api_key:
                    config.save_api_key(api_key)
                    console.print("[green]✓ fal.ai API 키가 저장되었습니다.[/green]")
                else:
                    console.print("[red]API 키를 입력해주세요.[/red]")
            elif choice == "2":
                console.print()
                api_key = Prompt.ask("[cyan]OpenAI API 키[/cyan]").strip()
                if api_key:
                    config.save_openai_api_key(api_key)
                    console.print("[green]✓ OpenAI API 키가 저장되었습니다.[/green]")
                else:
                    console.print("[red]API 키를 입력해주세요.[/red]")
            elif choice == "3":
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
                auth_method = Prompt.ask("[cyan]>>[/cyan]",
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


def show_invoice_menu() -> Optional[Dict[str, Any]]:
    """Invoice 관리 메뉴"""
    period_settings = {"start_date": None, "end_date": None, "days": 90}
    
    while True:
        console.print()
        console.print("[bold yellow]📧 Invoice 관리 (Gmail)[/bold yellow]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # 현재 설정 확인
        invoice_keywords_list = config.get_invoice_search_keywords()
        
        # 설정 정보 표시
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=16)
        info_table.add_column("값", style="white")
        
        # 키워드 리스트 표시
        if invoice_keywords_list:
            keywords_display = "\n".join([f"  • {kw}" for kw in invoice_keywords_list])
            info_table.add_row("검색 키워드", f"[green]({len(invoice_keywords_list)}개)\n{keywords_display}[/green]")
        else:
            info_table.add_row("검색 키워드", "[dim]없음[/dim]")
        
        # 검색 기간 표시
        if period_settings["start_date"]:
            period_str = f"{period_settings['start_date']} ~ {period_settings.get('end_date', '현재')}"
        else:
            period_str = f"최근 {period_settings['days']}일"
        info_table.add_row("검색 기간", f"[yellow]{period_str}[/yellow]")
        
        console.print(info_table)
        console.print()

        # 메뉴 옵션
        menu_table = Table(show_header=False, box=None, padding=(0, 2))
        menu_table.add_column("번호", style="bold cyan", width=4)
        menu_table.add_column("메뉴", style="white")
        
        menu_table.add_row("1", "Invoice 조회 및 Notion 저장")
        menu_table.add_row("2", "검색 키워드 추가")
        menu_table.add_row("3", "검색 키워드 삭제")
        menu_table.add_row("4", "검색 기간 설정")
        menu_table.add_row("5", "뒤로 가기")
        
        console.print(menu_table)

        try:
            choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3", "4", "5"])
            
            if choice == "1":
                # Invoice 조회 실행
                if not invoice_keywords_list:
                    console.print("[red]검색 키워드가 없습니다. 먼저 키워드를 추가해주세요.[/red]")
                    continue
                    
                return {
                    "action": "fetch",
                    "start_date": period_settings["start_date"],
                    "end_date": period_settings["end_date"],
                    "days": period_settings["days"]
                }
            elif choice == "2":
                # 검색 키워드 추가
                console.print()
                console.print("[bold cyan]검색 키워드 추가[/bold cyan]")
                console.print("[dim]" + "─" * 50 + "[/dim]")
                console.print()
                console.print("[dim]예: Your Replit receipt, AWS Invoice, etc.[/dim]")
                new_keyword = Prompt.ask("[cyan]추가할 검색 키워드[/cyan]").strip()
                
                if new_keyword:
                    if new_keyword in invoice_keywords_list:
                        console.print(f"[yellow]'{new_keyword}'는 이미 등록되어 있습니다.[/yellow]")
                    else:
                        invoice_keywords_list.append(new_keyword)
                        config.save_invoice_search_keywords(invoice_keywords_list)
                        console.print(f"[green]✓ '{new_keyword}'가 추가되었습니다.[/green]")
                else:
                    console.print("[red]키워드를 입력해주세요.[/red]")
                    
            elif choice == "3":
                # 검색 키워드 삭제
                if not invoice_keywords_list:
                    console.print("[yellow]삭제할 키워드가 없습니다.[/yellow]")
                    continue
                
                console.print()
                console.print("[bold yellow]검색 키워드 삭제[/bold yellow]")
                console.print("[dim]" + "─" * 50 + "[/dim]")
                console.print()
                
                # 키워드 목록 표시
                keyword_table = Table(show_header=False, box=None, padding=(0, 2))
                keyword_table.add_column("번호", style="bold cyan", width=4)
                keyword_table.add_column("키워드", style="white")
                
                for idx, kw in enumerate(invoice_keywords_list, 1):
                    keyword_table.add_row(str(idx), kw)
                
                console.print(keyword_table)
                
                try:
                    kw_choice = Prompt.ask("\n[yellow]삭제할 키워드 번호 (취소: 0)[/yellow]",
                                          choices=["0"] + [str(i) for i in range(1, len(invoice_keywords_list) + 1)])
                    
                    if kw_choice != "0":
                        deleted = invoice_keywords_list.pop(int(kw_choice) - 1)
                        config.save_invoice_search_keywords(invoice_keywords_list)
                        console.print(f"[green]✓ '{deleted}'가 삭제되었습니다.[/green]")
                except (ValueError, IndexError):
                    console.print("[red]올바른 번호를 선택해주세요.[/red]")
                    
            elif choice == "4":
                # 검색 기간 설정
                console.print()
                console.print("[bold magenta]📅 검색 기간 설정[/bold magenta]")
                console.print("[dim]" + "─" * 50 + "[/dim]")
                console.print()
                
                period_menu = Table(show_header=False, box=None, padding=(0, 2))
                period_menu.add_column("번호", style="bold cyan", width=4)
                period_menu.add_column("메뉴", style="white")
                
                period_menu.add_row("1", "최근 N일")
                period_menu.add_row("2", "시작/종료 날짜 직접 입력")
                period_menu.add_row("3", "취소")
                
                console.print(period_menu)
                
                period_choice = Prompt.ask("\n[cyan]선택[/cyan]", choices=["1", "2", "3"])
                
                if period_choice == "1":
                    console.print()
                    days_input = Prompt.ask("[cyan]최근 며칠[/cyan]", default=str(period_settings["days"]))
                    try:
                        days = int(days_input)
                        if days > 0:
                            period_settings["days"] = days
                            period_settings["start_date"] = None
                            period_settings["end_date"] = None
                            console.print(f"[green]✓ 검색 기간이 최근 {days}일로 설정되었습니다.[/green]")
                        else:
                            console.print("[red]양수를 입력해주세요.[/red]")
                    except ValueError:
                        console.print("[red]올바른 숫자를 입력해주세요.[/red]")
                        
                elif period_choice == "2":
                    console.print()
                    console.print("[dim]형식: YYYY-MM-DD[/dim]")
                    start = Prompt.ask("[cyan]시작 날짜[/cyan]").strip()
                    if start:
                        end = Prompt.ask("[cyan]종료 날짜 [dim](엔터 시 오늘)[/dim][/cyan]", default="").strip()
                        period_settings["start_date"] = start
                        period_settings["end_date"] = end if end else None
                        console.print(f"[green]✓ 검색 기간이 {start} ~ {end if end else '현재'}로 설정되었습니다.[/green]")
                    else:
                        console.print("[red]시작 날짜를 입력해주세요.[/red]")
                        
            elif choice == "5":
                return None
                
        except KeyboardInterrupt:
            return None
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
