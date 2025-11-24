"""
CLI 인터랙티브 메뉴 모듈
사용자 인터페이스 및 메뉴 관리 (Updated with questionary)
"""
import sys
import argparse
from typing import Optional, Dict, Any, Tuple
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich import box
import questionary
from questionary import Choice, Style
import config
import date_utils

# Rich console 인스턴스
console = Console()

# Questionary 스타일 설정
custom_style = Style([
    ('qmark', 'fg:#00ff00 bold'),       # 질문 앞 마크 (초록색)
    ('question', 'bold'),               # 질문 텍스트
    ('answer', 'fg:#00ffff bold'),      # 선택된 답변 (하늘색)
    ('pointer', 'fg:#00ff00 bold'),     # 선택 포인터 (초록색)
    ('highlighted', 'fg:#00ff00 bold'), # 하이라이트된 선택지 (초록색)
    ('selected', 'fg:#00ff00'),         # 선택된 항목
    ('separator', 'fg:#808080'),        # 구분선
    ('instruction', 'fg:#808080'),      # 설명 텍스트
    ('text', ''),                       # 일반 텍스트
    ('disabled', 'fg:#808080 italic')   # 비활성화된 항목
])


def show_main_menu() -> int:
    """메인 메뉴 표시"""
    console.print()
    console.print(Panel(
        "[bold blue]AI API 사용량 추적 CLI[/bold blue]",
        border_style="blue",
        padding=(1, 2),
        title="[bold]v1.0[/bold]",
        title_align="right"
    ))
    console.print()

    try:
        choice = questionary.select(
            "작업을 선택하세요:",
            choices=[
                Choice("  1. 공통 설정 (API 키, DB 설정)", value=1),
                Choice("  2. fal ai 사용량 추적", value=2),
                Choice("  3. Invoices 수집", value=3),
                questionary.Separator(),
                Choice("  0. 종료", value=0),
            ],
            style=custom_style,
            use_indicator=True,
            pointer="❯",
            qmark="?"
        ).ask()

        if choice is None:
            sys.exit(0)
        return choice

    except KeyboardInterrupt:
        console.print("\n[yellow]프로그램을 종료합니다.[/yellow]")
        sys.exit(0)


def show_common_settings_menu() -> None:
    """공통 설정 메뉴"""
    while True:
        console.clear()
        console.print()
        console.print("[bold cyan]>> 공통 설정[/bold cyan]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        try:
            choice = questionary.select(
                "설정 항목을 선택하세요:",
                choices=[
                    Choice("  1. API 키 설정 (fal ai, OpenAI, Notion)", value="1"),
                    Choice("  2. Notion DB 설정 (fal_ai, invoice)", value="2"),
                    questionary.Separator(),
                    Choice("  0. 뒤로 가기", value="0"),
                ],
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                show_api_key_menu()
            elif choice == "2":
                show_notion_database_menu()
            elif choice == "0" or choice is None:
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def show_model_menu() -> None:
    """모델 관리 메뉴"""
    while True:
        console.clear()
        models = config.get_models()
        console.print()
        console.print("[bold cyan]>> 모델 관리[/bold cyan]")
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

        try:
            choices = [
                Choice("  1. 모델 추가", value="1"),
            ]
            if models:
                choices.append(Choice("  2. 모델 삭제", value="2"))
            
            choices.append(questionary.Separator())
            choices.append(Choice("  3. 뒤로 가기", value="3"))

            choice = questionary.select(
                "작업을 선택하세요:",
                choices=choices,
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                add_model()
            elif choice == "2":
                if models:
                    delete_model()
                else:
                    console.print("[yellow]삭제할 모델이 없습니다.[/yellow]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            elif choice == "3" or choice is None:
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def add_model() -> None:
    """모델 추가"""
    console.print()
    console.print("[bold cyan]➕ 모델 추가[/bold cyan]")
    console.print("[dim]" + "─" * 50 + "[/dim]")
    
    model_id = questionary.text(
        "모델 ID를 입력하세요 (예: fal-ai/imagen4/preview/ultra):",
        style=custom_style
    ).ask()

    if not model_id:
        return

    model_id = model_id.strip()
    models = config.get_models()
    if model_id in models:
        console.print(f"[yellow]'{model_id}'는 이미 등록되어 있습니다.[/yellow]")
        questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
        return

    models.append(model_id)
    config.save_models(models)
    console.print(f"[green]✓ '{model_id}'가 추가되었습니다.[/green]")
    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def delete_model() -> None:
    """모델 삭제"""
    models = config.get_models()
    if not models:
        return

    console.print()
    console.print("[bold yellow]➖ 모델 삭제[/bold yellow]")
    
    choices = [Choice(model, value=i) for i, model in enumerate(models)]
    choices.append(Choice("취소", value=-1))

    idx = questionary.select(
        "삭제할 모델을 선택하세요:",
        choices=choices,
        style=custom_style,
        use_indicator=True
    ).ask()

    if idx == -1 or idx is None:
        return

    deleted = models.pop(idx)
    config.save_models(models)
    console.print(f"[green]✓ '{deleted}'가 삭제되었습니다.[/green]")
    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def show_date_range_menu(args: argparse.Namespace) -> Dict[str, Any]:
    """날짜 범위 설정 메뉴"""
    date_settings = {
        "preset": None,
        "start_date": None,
        "end_date": None
    }

    while True:
        console.clear()
        console.print()
        console.print("[bold magenta]>> 날짜 범위 설정[/bold magenta]")
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

        try:
            choice = questionary.select(
                "설정 방식을 선택하세요:",
                choices=[
                    Choice("  1. 프리셋 선택 (오늘, 어제, 최근 7일 등)", value="1"),
                    Choice("  2. 시작/종료 날짜 직접 입력", value="2"),
                    questionary.Separator(),
                    Choice("  3. 뒤로 가기", value="3"),
                ],
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

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
            elif choice == "3" or choice is None:
                return date_settings
        except KeyboardInterrupt:
            return date_settings
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def select_preset() -> Optional[str]:
    """프리셋 선택"""
    choices = [
        Choice("오늘 (today)", value="today"),
        Choice("어제 (yesterday)", value="yesterday"),
        Choice("최근 7일 (last-7-days)", value="last-7-days"),
        Choice("최근 30일 (last-30-days)", value="last-30-days"),
        Choice("이번 달 (this-month)", value="this-month"),
        Choice("취소", value=None)
    ]
    
    return questionary.select(
        "프리셋을 선택하세요:",
        choices=choices,
        style=custom_style,
        use_indicator=True,
        pointer="❯"
    ).ask()


def input_custom_date_range() -> Tuple[Optional[str], Optional[str]]:
    """사용자 정의 날짜 범위 입력"""
    console.print()
    console.print("[bold magenta]>> 날짜 범위 직접 입력[/bold magenta]")
    console.print("[dim]형식: YYYY-MM-DD[/dim]")

    try:
        start = questionary.text("시작 날짜 (YYYY-MM-DD):", style=custom_style).ask()
        if not start:
            console.print("[red]시작 날짜를 입력해주세요.[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            return None, None

        end = questionary.text("종료 날짜 (YYYY-MM-DD, 엔터 시 현재):", style=custom_style).ask()
        return start.strip(), end.strip() if end else None
    except KeyboardInterrupt:
        return None, None
    except Exception:
        return None, None


def show_api_key_menu() -> None:
    """API 키 설정 메뉴"""
    while True:
        console.clear()
        console.print()
        console.print("[bold green]>> API 키 설정[/bold green]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # fal.ai API 키 확인
        fal_api_key = config.get_api_key()
        fal_status = f"[green]{fal_api_key[:8]}...{fal_api_key[-4:]}[/green]" if fal_api_key else "[dim]등록된 API 키 없음[/dim]"

        # OpenAI API 키 확인
        openai_api_key = config.get_openai_api_key()
        openai_status = f"[green]{openai_api_key[:8]}...{openai_api_key[-4:]}[/green]" if openai_api_key else "[dim]등록된 API 키 없음[/dim]"

        # Notion API 키 확인
        notion_api_key = config.get_notion_api_key()
        notion_status = f"[green]{notion_api_key[:8]}...{notion_api_key[-4:]}[/green]" if notion_api_key else "[dim]등록된 API 키 없음[/dim]"

        # 현재 설정 표시
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=16)
        info_table.add_column("값", style="white")
        info_table.add_row("fal.ai API 키", fal_status)
        info_table.add_row("OpenAI API 키", openai_status)
        info_table.add_row("Notion API 키", notion_status)

        console.print(info_table)
        console.print()

        try:
            choice = questionary.select(
                "설정할 키를 선택하세요:",
                choices=[
                    Choice("  1. fal.ai API 키 입력/변경", value="1"),
                    Choice("  2. OpenAI API 키 입력/변경", value="2"),
                    Choice("  3. Notion API 키 입력/변경", value="3"),
                    questionary.Separator(),
                    Choice("  0. 뒤로 가기", value="0"),
                ],
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                api_key = questionary.password("fal.ai Admin API 키:", style=custom_style).ask()
                if api_key:
                    config.save_api_key(api_key.strip())
                    console.print("[green]✓ fal.ai API 키가 저장되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            elif choice == "2":
                api_key = questionary.password("OpenAI API 키:", style=custom_style).ask()
                if api_key:
                    config.save_openai_api_key(api_key.strip())
                    console.print("[green]✓ OpenAI API 키가 저장되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            elif choice == "3":
                api_key = questionary.password("Notion API 키:", style=custom_style).ask()
                if api_key:
                    config.save_notion_api_key(api_key.strip())
                    console.print("[green]✓ Notion API 키가 저장되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            elif choice == "0" or choice is None:
                break
        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def show_notion_database_menu() -> None:
    """Notion 데이터베이스 설정 메뉴"""
    while True:
        console.clear()
        console.print()
        console.print("[bold blue]>> Notion DB 설정[/bold blue]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # fal_ai, invoice DB ID 확인
        fal_ai_db = config.get_notion_database_id("fal_ai")
        invoice_db = config.get_notion_database_id("invoice")

        # 현재 설정 표시
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=18)
        info_table.add_column("값", style="white")

        info_table.add_row("fal_ai DB ID", f"[green]{fal_ai_db[:8]}...{fal_ai_db[-4:]}[/green]" if fal_ai_db else "[dim]미설정[/dim]")
        info_table.add_row("invoice DB ID", f"[green]{invoice_db[:8]}...{invoice_db[-4:]}[/green]" if invoice_db else "[dim]미설정[/dim]")

        console.print(info_table)
        console.print()

        try:
            choice = questionary.select(
                "설정할 DB를 선택하세요:",
                choices=[
                    Choice("  1. fal_ai DB ID 설정", value="1"),
                    Choice("  2. invoice DB ID 설정", value="2"),
                    questionary.Separator(),
                    Choice("  0. 뒤로 가기", value="0"),
                ],
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                console.print("[dim]fal.ai 사용량 데이터를 저장할 Notion 데이터베이스 ID를 입력하세요.[/dim]")
                db_id = questionary.text("fal_ai DB ID:", style=custom_style).ask()
                if db_id:
                    config.save_notion_database_id("fal_ai", db_id.strip())
                    console.print("[green]✓ fal_ai DB ID가 저장되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            elif choice == "2":
                console.print("[dim]Invoice 데이터를 저장할 Notion 데이터베이스 ID를 입력하세요.[/dim]")
                db_id = questionary.text("invoice DB ID:", style=custom_style).ask()
                if db_id:
                    config.save_notion_database_id("invoice", db_id.strip())
                    console.print("[green]✓ invoice DB ID가 저장되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
            elif choice == "0" or choice is None:
                break

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def show_fal_ai_menu(args: argparse.Namespace) -> Optional[Dict[str, Any]]:
    """fal.ai 사용량 추적 메뉴"""
    while True:
        console.clear()
        console.print()
        console.print("[bold green]>> fal.ai 사용량 추적[/bold green]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # 현재 설정 확인
        models = config.get_models()
        api_key = config.get_api_key()

        # 날짜 범위 표시
        try:
            start, end = date_utils.parse_date_range(
                preset=args.preset,
                start_date=args.start_date,
                end_date=args.end_date,
                tz=args.timezone or config.get_timezone()
            )
            start_display = start.strftime("%Y-%m-%d")
            end_display = end.strftime("%Y-%m-%d")
            date_range_display = f"[yellow]{start_display} ~ {end_display}[/yellow]"
        except:
            date_range_display = "[dim]미설정[/dim]"

        # 설정 정보 표시
        info_table = Table(show_header=False, box=None, padding=(0, 1))
        info_table.add_column("항목", style="cyan", width=16)
        info_table.add_column("값", style="white")

        info_table.add_row("API 키", f"[green]등록됨[/green]" if api_key else "[red]미설정[/red]")
        info_table.add_row("모델", f"[green]{len(models)}개 등록[/green]" if models else "[dim]없음[/dim]")
        info_table.add_row("조회 기간", date_range_display)

        console.print(info_table)
        console.print()

        try:
            choice = questionary.select(
                "작업을 선택하세요:",
                choices=[
                    Choice("  1. 모델 관리", value="1"),
                    Choice("  2. 날짜 범위 설정", value="2"),
                    Choice("  3. 조회 실행", value="3"),
                    questionary.Separator(),
                    Choice("  0. 뒤로 가기", value="0"),
                ],
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                show_model_menu()
            elif choice == "2":
                date_settings = show_date_range_menu(args)
                if date_settings.get("preset"):
                    args.preset = date_settings["preset"]
                    args.start_date = None
                    args.end_date = None
                elif date_settings.get("start_date"):
                    args.preset = None
                    args.start_date = date_settings["start_date"]
                    args.end_date = date_settings.get("end_date")
            elif choice == "3":
                return {"action": "query"}
            elif choice == "0" or choice is None:
                return None

        except KeyboardInterrupt:
            return None
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def show_invoice_keyword_menu() -> None:
    """Invoice 검색 키워드 설정 메뉴"""
    while True:
        console.clear()
        console.print()
        console.print("[bold cyan]>> 검색 키워드 설정[/bold cyan]")
        console.print("[dim]" + "─" * 50 + "[/dim]")
        console.print()

        # 현재 키워드 목록
        keywords_list = config.get_invoice_search_keywords()

        if keywords_list:
            keyword_table = Table(show_header=True, box=box.SIMPLE, border_style="cyan")
            keyword_table.add_column("번호", style="cyan", width=6)
            keyword_table.add_column("키워드", style="white")

            for idx, kw in enumerate(keywords_list, 1):
                keyword_table.add_row(str(idx), kw)

            console.print(keyword_table)
        else:
            console.print("[dim]등록된 키워드가 없습니다.[/dim]")

        console.print()

        try:
            choices = [Choice("  1. 키워드 추가", value="1")]
            if keywords_list:
                choices.append(Choice("  2. 키워드 삭제", value="2"))
            choices.append(Choice("  0. 뒤로 가기", value="0"))

            choice = questionary.select(
                "작업을 선택하세요:",
                choices=choices,
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                console.print("[dim]예: Your Replit receipt, AWS Invoice[/dim]")
                new_keyword = questionary.text("추가할 검색 키워드:", style=custom_style).ask()
                
                if new_keyword:
                    new_keyword = new_keyword.strip()
                    if new_keyword in keywords_list:
                        console.print(f"[yellow]'{new_keyword}'는 이미 등록되어 있습니다.[/yellow]")
                    else:
                        keywords_list.append(new_keyword)
                        config.save_invoice_search_keywords(keywords_list)
                        console.print(f"[green]✓ '{new_keyword}'가 추가되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()

            elif choice == "2":
                kw_choices = [Choice(kw, value=i) for i, kw in enumerate(keywords_list)]
                kw_choices.append(Choice("취소", value=-1))
                
                idx = questionary.select(
                    "삭제할 키워드를 선택하세요:",
                    choices=kw_choices,
                    style=custom_style,
                    use_indicator=True
                ).ask()

                if idx != -1 and idx is not None:
                    deleted = keywords_list.pop(idx)
                    config.save_invoice_search_keywords(keywords_list)
                    console.print(f"[green]✓ '{deleted}'가 삭제되었습니다.[/green]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()

            elif choice == "0" or choice is None:
                break

        except KeyboardInterrupt:
            break
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()


def show_invoice_menu() -> Optional[Dict[str, Any]]:
    """Invoice 수집 메뉴"""
    period_settings = {"start_date": None, "end_date": None, "days": 90}

    while True:
        console.clear()
        console.print()
        console.print("[bold yellow]>> Invoices 수집[/bold yellow]")
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
            keywords_display = ", ".join(invoice_keywords_list[:3])
            if len(invoice_keywords_list) > 3:
                keywords_display += f" 외 {len(invoice_keywords_list) - 3}개"
            info_table.add_row("검색 키워드", f"[green]{keywords_display}[/green]")
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

        try:
            choice = questionary.select(
                "작업을 선택하세요:",
                choices=[
                    Choice("  1. 검색 키워드 설정 (추가/삭제)", value="1"),
                    Choice("  2. 검색 기간 설정", value="2"),
                    Choice("  3. 조회 실행", value="3"),
                    Choice("  0. 뒤로 가기", value="0"),
                ],
                style=custom_style,
                use_indicator=True,
                pointer="❯"
            ).ask()

            if choice == "1":
                show_invoice_keyword_menu()
            elif choice == "2":
                p_choice = questionary.select(
                    "기간 설정 방식:",
                    choices=[
                        Choice("1. 최근 N일", value="1"),
                        Choice("2. 시작/종료 날짜 직접 입력", value="2"),
                        Choice("0. 취소", value="0"),
                    ],
                    style=custom_style,
                    use_indicator=True,
                    pointer="❯"
                ).ask()

                if p_choice == "1":
                    days = questionary.text(
                        "최근 며칠 (기본: 90):", 
                        default=str(period_settings["days"]),
                        style=custom_style
                    ).ask()
                    if days and days.isdigit():
                        period_settings["days"] = int(days)
                        period_settings["start_date"] = None
                        period_settings["end_date"] = None
                
                elif p_choice == "2":
                    start = questionary.text("시작 날짜 (YYYY-MM-DD):", style=custom_style).ask()
                    if start:
                        end = questionary.text("종료 날짜 (엔터 시 오늘):", style=custom_style).ask()
                        period_settings["start_date"] = start.strip()
                        period_settings["end_date"] = end.strip() if end else None

            elif choice == "3":
                if not invoice_keywords_list:
                    console.print("[red]검색 키워드가 없습니다. 먼저 키워드를 추가해주세요.[/red]")
                    questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
                    continue

                return {
                    "action": "fetch",
                    "start_date": period_settings["start_date"],
                    "end_date": period_settings["end_date"],
                    "days": period_settings["days"]
                }
            elif choice == "0" or choice is None:
                return None

        except KeyboardInterrupt:
            return None
        except Exception as e:
            console.print(f"[red]오류: {e}[/red]")
            questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=custom_style).ask()
