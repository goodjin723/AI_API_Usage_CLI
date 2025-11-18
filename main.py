"""
fal.ai 사용량 추적 CLI
메인 실행 로직 및 핵심 기능
"""
import sys
from typing import Optional, List, Dict, Any
from datetime import datetime
from rich.console import Console
from rich.prompt import Prompt
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

        for auth_method, records in notion_data_by_auth.items():
            if verbose:
                console.print(f"\n[dim][DEBUG] 처리 중인 auth_method: '{auth_method}' ({len(records)}개 레코드)[/dim]")

            # 데이터베이스 ID 가져오기 (우선순위: CLI 맵 > CLI 공통 > config.json)
            database_id = None
            if cli_database_map:
                # 1. 해당 auth_method의 database_id가 CLI 맵에 있는지 확인
                if auth_method in cli_database_map:
                    database_id = cli_database_map[auth_method]
                # 2. "__all__" 키가 있으면 모든 auth_method에 적용
                elif "__all__" in cli_database_map:
                    database_id = cli_database_map["__all__"]

            # 3. CLI에 없으면 config.json에서 가져오기
            if not database_id:
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
            save_to_notion(usage_data, args.notion_api_key, args.notion_database_id, args.dry_run, args.verbose, args.update_existing)

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


def interactive_mode(args) -> None:
    """인터랙티브 모드"""
    date_settings = {}

    while True:
        choice = cli_menus.show_main_menu()

        if choice == 1:
            cli_menus.show_model_menu()
        elif choice == 2:
            date_settings = cli_menus.show_date_range_menu(args)
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
            cli_menus.show_api_key_menu()
        elif choice == 4:
            cli_menus.show_notion_menu()
        elif choice == 5:
            cli_menus.show_notion_save_menu(args)
        elif choice == 6:
            validate_and_execute_query(args)
            Prompt.ask("\n[dim]계속하려면 엔터를 누르세요[/dim]", default="")
        elif choice == 7:
            console.print("\n[yellow]프로그램을 종료합니다.[/yellow]")
            break


def cli_mode(args) -> None:
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
