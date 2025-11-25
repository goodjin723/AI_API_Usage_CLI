"""
fal.ai 사용량 추적 CLI
메인 실행 로직 및 핵심 기능
"""
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt
import questionary
import api_client
import config
import date_utils
import formatter
import usage_tracker
import notion_integration
import cli_args
import cli_menus

# Rich console 인스턴스
console = Console()


def get_models_from_args(args) -> List[str]:
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


def parse_date_range(args) -> tuple[datetime, datetime]:
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


def validate_and_execute_query(args) -> None:
    """필수 값 검증 후 조회 실행"""
    # API 키 확인
    api_key = config.get_api_key(args.fal_ai_api_key)
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
    cli_notion_database_id: Optional[str],
    dry_run: bool,
    verbose: bool,
    update_existing: bool = False
) -> None:
    """Notion에 데이터 저장"""
    try:
        # CLI 인자로 전달된 database_id를 파싱
        cli_database_map = {}
        if cli_notion_database_id:
            # 쉼표로 구분된 여러 개의 "키:값" 쌍 파싱
            if "," in cli_notion_database_id:
                for pair in cli_notion_database_id.split(","):
                    pair = pair.strip()
                    if ":" in pair:
                        key, db_id = pair.split(":", 1)
                        cli_database_map[key.strip()] = db_id.strip()
            # 단일 "키:값" 또는 UUID만 있는 경우
            elif ":" in cli_notion_database_id:
                key, db_id = cli_notion_database_id.split(":", 1)
                cli_database_map[key.strip()] = db_id.strip()
            else:
                # UUID만 있는 경우 (모든 auth_method에 적용)
                cli_database_map["__all__"] = cli_notion_database_id.strip()

        if verbose and cli_database_map:
            console.print(f"\n[dim][DEBUG] CLI 데이터베이스 맵: {cli_database_map}[/dim]")

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

        # 통합 데이터베이스 ID 가져오기 (모든 auth_method에 대해 하나의 DB 사용)
        database_id = None
        if cli_database_map:
            # CLI에서 "__all__" 키가 있으면 사용
            if "__all__" in cli_database_map:
                database_id = cli_database_map["__all__"]
            # 또는 첫 번째 키의 값 사용
            elif cli_database_map:
                database_id = list(cli_database_map.values())[0]

        # CLI에 없으면 config.json에서 통합 DB 가져오기
        if not database_id:
            database_id = config.get_fal_ai_database_id()

        # 데이터베이스 ID가 없으면 오류
        if not database_id:
            console.print("\n[red]fal.ai 통합 Notion 데이터베이스 ID가 설정되지 않았습니다.[/red]")
            console.print("[cyan]해결 방법:[/cyan]")
            console.print("[dim]  1. 인터랙티브 메뉴에서 '4. Notion 설정' > '2. 데이터베이스 ID 추가/수정' 선택[/dim]")
            console.print("[dim]  2. 키 별칭에 'fal_ai' 입력[/dim]")
            console.print("[dim]  3. 통합 데이터베이스 ID 입력[/dim]")
            total_skipped = sum(len(records) for records in notion_data_by_auth.values())
            return

        # 데이터베이스 존재 여부 확인 (한 번만)
        if verbose:
            console.print(f"[dim][DEBUG] 통합 데이터베이스 ID 확인 중: {database_id}[/dim]")
        if not notion.check_database_exists(database_id, verbose=verbose):
            console.print(f"\n[red]통합 데이터베이스(ID: {database_id})를 찾을 수 없습니다.[/red]")
            total_skipped = sum(len(records) for records in notion_data_by_auth.values())
            return

        # 모든 auth_method의 데이터를 하나의 DB에 저장
        if verbose:
            total_records = sum(len(records) for records in notion_data_by_auth.values())
            console.print(f"\n[cyan]통합 데이터베이스에 저장 중... (총 {total_records}개 레코드)[/cyan]")
        if update_existing:
            console.print(f"[yellow]중복 데이터 발견 시 업데이트 모드[/yellow]")
        else:
            console.print(f"[yellow]중복 데이터 발견 시 스킵 모드 (중복 방지)[/yellow]")

        # 모든 레코드를 하나의 리스트로 합치기
        all_records = []
        for auth_method, records in notion_data_by_auth.items():
            if verbose:
                console.print(f"[dim][DEBUG] '{auth_method}': {len(records)}개 레코드 추가[/dim]")
            all_records.extend(records)

        # 통합 DB에 저장
        stats = notion.save_usage_data(database_id, all_records, update_existing=update_existing, verbose=verbose)
        total_created = stats["created"]
        total_updated = stats["updated"]
        total_skipped = stats["skipped"]

        if verbose:
            console.print(f"[green]생성: {stats['created']}, 업데이트: {stats['updated']}, 스킵: {stats['skipped']}[/green]")

        console.print(f"\n[green]✓ Notion 저장 완료 (생성: {total_created}, 업데이트: {total_updated}, 스킵: {total_skipped})[/green]")

    except Exception as e:
        console.print(f"\n[red]Notion 저장 중 오류 발생: {e}[/red]")
        if verbose:
            import traceback
            traceback.print_exc()


def execute_query(
    args,
    api_key: str,
    models: List[str],
    start: datetime,
    end: datetime
) -> None:
    """실제 조회 실행"""
    try:
        console.print()

        # 1단계: 준비
        console.print()
        with console.status("[bold cyan]API 호출 준비 중...[/bold cyan]", spinner="dots"):
            if args.verbose:
                console.print(f"[dim]   모델 목록: {', '.join(models)}[/dim]")
                start_display = start.strftime("%Y-%m-%d %H:%M:%S")
                end_display = end.strftime("%Y-%m-%d %H:%M:%S")
                console.print(f"[dim]   조회 기간: {start_display} ~ {end_display}[/dim]")

            timezone = args.timezone or config.get_timezone()

            # API 클라이언트 생성
            client = api_client.FalAPIClient(api_key)

            # 2단계: Usage API 호출
            console.print("[dim]사용량 데이터 조회 중...[/dim]")

            usage_data = client.get_usage(
                endpoint_ids=models,
                start=start,
                end=end,
                timeframe=args.timeframe,
                timezone=timezone,
                bound_to_timeframe=args.bound_to_timeframe,
                include_notion=True
            )

        console.print("[green]✓ 데이터 조회 완료[/green]")

        # 3단계: 데이터 처리 및 출력
        formatter.format_for_display(usage_data)

        # 4단계: Notion 저장 확인
        console.print()
        save_choice = questionary.confirm(
            "Notion에 저장하시겠습니까?",
            default=True,
            style=cli_menus.custom_style
        ).ask()

        if save_choice:
            # Notion API 키 확인
            notion_api_key = config.get_notion_api_key(args.notion_api_key)
            if not notion_api_key:
                console.print("[red]Notion API 키가 설정되지 않았습니다.[/red]")
                console.print("[yellow]메뉴에서 '공통 설정 > API 키 설정'을 선택하여 API 키를 설정해주세요.[/yellow]")
                return

            # fal_ai 데이터베이스 ID 확인
            fal_ai_db_id = config.get_fal_ai_database_id()
            if not fal_ai_db_id:
                console.print("[red]fal.ai Notion 데이터베이스 ID가 설정되지 않았습니다.[/red]")
                console.print("[yellow]메뉴에서 '공통 설정 > Notion DB 설정'을 선택하여 fal_ai DB ID를 설정해주세요.[/yellow]")
                return

            # 중복 업데이트 옵션
            update_existing = questionary.confirm(
                "중복된 데이터를 업데이트하시겠습니까?",
                default=False,
                style=cli_menus.custom_style
            ).ask()

            with console.status("[bold cyan]Notion에 저장 중...[/bold cyan]", spinner="dots"):
                save_to_notion(usage_data, args.notion_api_key, None, args.dry_run, args.verbose, update_existing)
        else:
            console.print("[yellow]저장을 취소했습니다.[/yellow]")

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
        args = cli_args.parse_args()

        # CLI 인자가 모두 비어있으면 인터랙티브 모드
        # 기본값이 설정된 인자는 제외하고, 실제로 사용자가 명시한 인자만 체크
        has_cli_args = any([
            args.fal_ai_api_key,
            args.models,
            args.preset,
            args.start_date,
            args.end_date,
            args.timezone,  # 기본값이 None이므로 그대로 체크
            args.notion,
            args.verbose,
            args.dry_run,
            args.invoice,  # Invoice 모드
            args.invoice_keywords,
            args.invoice_start_date,
            args.invoice_end_date
            # args.timeframe, args.bound_to_timeframe, args.invoice_days는 기본값이 있으므로 제외
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


def interactive_mode(args) -> None:
    """인터랙티브 모드"""
    while True:
        choice = cli_menus.show_main_menu()

        if choice == 0:
            # 종료
            console.print("\n[yellow]프로그램을 종료합니다.[/yellow]")
            break
        elif choice == 1:
            # 공통 설정
            cli_menus.show_common_settings_menu()
        elif choice == 2:
            # fal ai 사용량 추적
            fal_result = cli_menus.show_fal_ai_menu(args)
            if fal_result and fal_result.get("action") == "query":
                validate_and_execute_query(args)
                questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=cli_menus.custom_style).ask()
        elif choice == 3:
            # invoices 수집
            invoice_result = cli_menus.show_invoice_menu()
            if invoice_result and invoice_result.get("action") == "fetch":
                execute_invoice_query(invoice_result, args)
                questionary.press_any_key_to_continue("계속하려면 아무 키나 누르세요...", style=cli_menus.custom_style).ask()


def execute_invoice_query(invoice_settings: Dict[str, Any], args) -> None:
    """Invoice 조회 및 Notion 저장"""
    try:
        import invoice_gmail_client
        
        console.print()
        console.print("[cyan]⏳ Invoice 조회 준비 중...[/cyan]")
        
        # 설정 확인
        start_date = invoice_settings.get("start_date")
        end_date = invoice_settings.get("end_date")
        days = invoice_settings.get("days", 90)
        
        if args.verbose:
            if start_date:
                console.print(f"[dim]   검색 기간: {start_date} ~ {end_date or '현재'}[/dim]")
            else:
                console.print(f"[dim]   검색 기간: 최근 {days}일[/dim]")
        
        # Invoice 조회
        console.print()
        with console.status("[bold cyan]Gmail에서 Invoice 검색 중...[/bold cyan]", spinner="dots"):
            invoices = invoice_gmail_client.fetch_invoices(
                search_keywords=None,  # config에서 가져옴
                model="gpt-4o-mini",
                start_date=start_date,
                end_date=end_date,
                days=days,
                verbose=args.verbose,
                openai_api_key=args.open_ai_api_key
            )
        
        if not invoices:
            console.print("[yellow]⚠ 검색된 Invoice가 없습니다.[/yellow]")
            return

        console.print(f"[green]✓ {len(invoices)}개 Invoice 발견[/green]")

        # 테이블 형식으로 결과 표시
        formatter.format_invoices_for_display(invoices)

        # Notion 저장 확인
        console.print()
        save_choice = questionary.confirm(
            "Notion에 저장하시겠습니까?",
            default=True,
            style=cli_menus.custom_style
        ).ask()
        
        if save_choice:
            # Notion API 키 확인
            notion_api_key = config.get_notion_api_key()
            if not notion_api_key:
                console.print("[red]Notion API 키가 설정되지 않았습니다.[/red]")
                console.print("[yellow]메뉴에서 '4. Notion 설정'을 선택하여 API 키를 설정해주세요.[/yellow]")
                return
            
            # Invoice 데이터베이스 ID 확인
            invoice_db_id = config.get_notion_database_id("invoice")
            if not invoice_db_id:
                console.print("[red]Invoice Notion 데이터베이스 ID가 설정되지 않았습니다.[/red]")
                console.print("[yellow]메뉴에서 '4. Notion 설정' > '2. 데이터베이스 ID 추가/수정'을 선택하세요.[/yellow]")
                console.print("[yellow]키 별칭: 'invoice'[/yellow]")
                return
            
            # Notion에 저장
            notion = notion_integration.NotionClient(notion_api_key)
            
            # 중복 업데이트 옵션
            update_existing = questionary.confirm(
                "중복된 Invoice를 업데이트하시겠습니까?",
                default=False,
                style=cli_menus.custom_style
            ).ask()

            with console.status("[bold cyan]Notion에 저장 중...[/bold cyan]", spinner="dots"):
                stats = notion.save_invoices(
                    database_id=invoice_db_id,
                    invoices=invoices,
                    update_existing=update_existing,
                    verbose=args.verbose
                )
            
            console.print(f"\n[green]✓ Notion 저장 완료 (생성: {stats['created']}, 업데이트: {stats['updated']}, 스킵: {stats['skipped']})[/green]")
        else:
            console.print("[yellow]저장을 취소했습니다.[/yellow]")
        
    except Exception as e:
        console.print(f"\n[red]❌ Invoice 조회 중 오류 발생: {e}[/red]")
        if args.verbose:
            import traceback
            traceback.print_exc()


def cli_mode(args) -> None:
    """CLI 모드 (기존 동작)"""
    if args.invoice:
        # Invoice 수집 모드
        cli_invoice_mode(args)
    else:
        # fal.ai 사용량 추적 모드 (기존 동작)
        cli_fal_ai_mode(args)


def cli_fal_ai_mode(args) -> None:
    """CLI 모드 - fal.ai 사용량 추적"""
    # API 키 가져오기
    api_key = config.get_api_key(args.fal_ai_api_key)
    if not api_key:
        raise ValueError(
            "fal.ai Admin API 키가 필요합니다. "
            "환경 변수 FAL_ADMIN_API_KEY를 설정하거나 -fal-ai-api-key 옵션을 사용하세요."
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


def cli_invoice_mode(args) -> None:
    """CLI 모드 - Invoice 수집"""
    import invoice_gmail_client

    # 키워드 가져오기 (CLI 인자 또는 config.json)
    keywords = None
    if args.invoice_keywords:
        keywords = [k.strip() for k in args.invoice_keywords.split(",") if k.strip()]
        if args.verbose:
            console.print(f"[dim]검색 키워드: {', '.join(keywords)}[/dim]")

    # 날짜 범위 설정
    start_date = args.invoice_start_date
    end_date = args.invoice_end_date
    days = args.invoice_days

    if args.verbose:
        if start_date:
            console.print(f"[dim]검색 기간: {start_date} ~ {end_date or '현재'}[/dim]")
        else:
            console.print(f"[dim]검색 기간: 최근 {days}일[/dim]")

    # Invoice 조회
    console.print()
    with console.status("[bold cyan]Gmail에서 Invoice 검색 중...[/bold cyan]", spinner="dots"):
        invoices = invoice_gmail_client.fetch_invoices(
            search_keywords=keywords,
            model="gpt-4o-mini",
            start_date=start_date,
            end_date=end_date,
            days=days,
            verbose=args.verbose,
            openai_api_key=args.open_ai_api_key
        )

    if not invoices:
        console.print("[yellow]검색된 Invoice가 없습니다.[/yellow]")
        return

    console.print(f"[green]✓ {len(invoices)}개 Invoice 발견[/green]")

    # 테이블 형식으로 결과 표시
    formatter.format_invoices_for_display(invoices)

    # Notion 저장 (args.notion이 True인 경우)
    if args.notion:
        # Notion API 키 확인
        notion_api_key = config.get_notion_api_key(args.notion_api_key)
        if not notion_api_key:
            console.print("[red]Notion API 키가 설정되지 않았습니다.[/red]")
            console.print("[yellow]환경 변수 NOTION_API_KEY를 설정하거나 -notion-api-key 옵션을 사용하세요.[/yellow]")
            return

        # Invoice 데이터베이스 ID 확인
        invoice_db_id = config.get_notion_database_id("invoice")
        if not invoice_db_id:
            console.print("[red]Invoice Notion 데이터베이스 ID가 설정되지 않았습니다.[/red]")
            console.print("[yellow]config.json에서 invoice 데이터베이스 ID를 설정해주세요.[/yellow]")
            return

        # Notion에 저장
        notion = notion_integration.NotionClient(notion_api_key)

        update_existing = args.update_existing

        with console.status("[bold cyan]Notion에 저장 중...[/bold cyan]", spinner="dots"):
            stats = notion.save_invoices(
                database_id=invoice_db_id,
                invoices=invoices,
                update_existing=update_existing,
                verbose=args.verbose
            )

        console.print(f"\n[green]✓ Notion 저장 완료 (생성: {stats['created']}, 업데이트: {stats['updated']}, 스킵: {stats['skipped']})[/green]")


if __name__ == "__main__":
    main()
