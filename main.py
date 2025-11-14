"""
fal.ai 사용량 추적 CLI
"""
import argparse
import sys
import json
from typing import Optional, List, Dict, Any
from datetime import datetime
import api_client
import config
import date_utils
import formatter


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
             "첫 실행 시 필수, 이후 실행 시 생략 가능 (config.json에 저장된 목록 자동 사용)"
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
        default=None,
        help="집계 단위 (미지정 시 API가 자동 감지하여 날짜별 상세 데이터 반환)"
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
        help="실제 저장 없이 미리보기만 (Notion 저장 시)"
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
    print("\n" + "="*60)
    print("fal.ai 사용량 추적 CLI")
    print("="*60)
    print("1. 모델 관리")
    print("2. 날짜 범위 설정")
    print("3. API 키 설정")
    print("4. 조회 실행")
    print("5. 종료")
    print("="*60)
    
    while True:
        try:
            choice = input("\n선택하세요 (1-5): ").strip()
            if choice in ["1", "2", "3", "4", "5"]:
                return int(choice)
            print("[ERROR] 1-5 사이의 숫자를 입력하세요.")
        except KeyboardInterrupt:
            print("\n\n프로그램을 종료합니다.")
            sys.exit(0)
        except Exception:
            print("[ERROR] 올바른 숫자를 입력하세요.")


def show_model_menu() -> None:
    """모델 관리 메뉴"""
    while True:
        models = config.get_models()
        print("\n" + "="*60)
        print("모델 관리")
        print("="*60)
        if models:
            print("\n현재 모델 목록:")
            for i, model in enumerate(models, 1):
                print(f"  {i}. {model}")
        else:
            print("\n등록된 모델이 없습니다.")
        print("\n1. 모델 추가")
        print("2. 모델 삭제")
        print("3. 뒤로 가기")
        print("="*60)
        
        try:
            choice = input("\n선택하세요 (1-3): ").strip()
            if choice == "1":
                add_model()
            elif choice == "2":
                if models:
                    delete_model()
                else:
                    print("[INFO] 삭제할 모델이 없습니다.")
            elif choice == "3":
                break
            else:
                print("[ERROR] 1-3 사이의 숫자를 입력하세요.")
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[ERROR] {e}")


def add_model() -> None:
    """모델 추가"""
    print("\n모델 추가")
    print("예: fal-ai/imagen4/preview/ultra")
    model_id = input("모델 ID를 입력하세요: ").strip()
    
    if not model_id:
        print("[ERROR] 모델 ID를 입력해주세요.")
        return
    
    models = config.get_models()
    if model_id in models:
        print(f"[INFO] '{model_id}'는 이미 등록되어 있습니다.")
        return
    
    models.append(model_id)
    config.save_models(models)
    print(f"[SUCCESS] '{model_id}'가 추가되었습니다.")


def delete_model() -> None:
    """모델 삭제"""
    models = config.get_models()
    if not models:
        print("[INFO] 삭제할 모델이 없습니다.")
        return
    
    print("\n모델 삭제")
    print("삭제할 모델 번호를 입력하세요:")
    for i, model in enumerate(models, 1):
        print(f"  {i}. {model}")
    
    try:
        choice = int(input("\n번호: ").strip())
        if 1 <= choice <= len(models):
            deleted = models.pop(choice - 1)
            config.save_models(models)
            print(f"[SUCCESS] '{deleted}'가 삭제되었습니다.")
        else:
            print(f"[ERROR] 1-{len(models)} 사이의 숫자를 입력하세요.")
    except ValueError:
        print("[ERROR] 올바른 숫자를 입력하세요.")
    except Exception as e:
        print(f"[ERROR] {e}")


def show_date_range_menu() -> Dict[str, Any]:
    """날짜 범위 설정 메뉴"""
    date_settings = {
        "preset": None,
        "start_date": None,
        "end_date": None
    }
    
    while True:
        print("\n" + "="*60)
        print("날짜 범위 설정")
        print("="*60)
        print("1. 프리셋 선택 (오늘, 어제, 최근 7일 등)")
        print("2. 시작/종료 날짜 직접 입력")
        print("3. 뒤로 가기")
        print("="*60)
        
        try:
            choice = input("\n선택하세요 (1-3): ").strip()
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
            else:
                print("[ERROR] 1-3 사이의 숫자를 입력하세요.")
        except KeyboardInterrupt:
            return date_settings
        except Exception as e:
            print(f"[ERROR] {e}")


def select_preset() -> Optional[str]:
    """프리셋 선택"""
    print("\n프리셋 선택:")
    print("1. 오늘 (today)")
    print("2. 어제 (yesterday)")
    print("3. 최근 7일 (last-7-days)")
    print("4. 최근 30일 (last-30-days)")
    print("5. 이번 달 (this-month)")
    print("6. 취소")
    
    presets = {
        "1": "today",
        "2": "yesterday",
        "3": "last-7-days",
        "4": "last-30-days",
        "5": "this-month"
    }
    
    try:
        choice = input("\n선택하세요 (1-6): ").strip()
        if choice == "6":
            return None
        if choice in presets:
            return presets[choice]
        print("[ERROR] 1-6 사이의 숫자를 입력하세요.")
        return None
    except Exception:
        return None


def input_custom_date_range() -> tuple[Optional[str], Optional[str]]:
    """사용자 정의 날짜 범위 입력"""
    print("\n날짜 범위 입력 (YYYY-MM-DD 형식)")
    start = input("시작 날짜: ").strip()
    end = input("종료 날짜 (엔터 시 현재 날짜): ").strip()
    
    if not start:
        print("[ERROR] 시작 날짜를 입력해주세요.")
        return None, None
    
    return start, end if end else None


def show_api_key_menu() -> None:
    """API 키 설정 메뉴"""
    print("\n" + "="*60)
    print("API 키 설정")
    print("="*60)
    
    api_key = config.get_api_key()
    if api_key:
        # 마스킹 처리
        masked_key = api_key[:8] + "..." + api_key[-4:] if len(api_key) > 12 else "***"
        print(f"\n현재 API 키: {masked_key}")
    else:
        print("\n등록된 API 키가 없습니다.")
    
    print("\n1. API 키 입력/변경")
    print("2. 뒤로 가기")
    print("="*60)
    
    try:
        choice = input("\n선택하세요 (1-2): ").strip()
        if choice == "1":
            api_key = input("\nfal.ai Admin API 키를 입력하세요: ").strip()
            if api_key:
                config.save_api_key(api_key)
                print("[SUCCESS] API 키가 저장되었습니다.")
            else:
                print("[ERROR] API 키를 입력해주세요.")
        elif choice != "2":
            print("[ERROR] 1-2 사이의 숫자를 입력하세요.")
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"[ERROR] {e}")


def validate_and_execute_query(args: argparse.Namespace) -> None:
    """필수 값 검증 후 조회 실행"""
    # API 키 확인
    api_key = config.get_api_key(args.api_key)
    if not api_key:
        print("\n[ERROR] API 키가 설정되지 않았습니다.")
        print("메뉴에서 '3. API 키 설정'을 선택하여 API 키를 설정해주세요.")
        return
    
    # 모델 목록 확인
    models = get_models_from_args(args)
    if not models:
        print("\n[ERROR] 모델 목록이 비어있습니다.")
        print("메뉴에서 '1. 모델 관리'를 선택하여 모델을 추가해주세요.")
        return
    
    # 날짜 범위 확인
    try:
        start, end = parse_date_range(args)
    except Exception as e:
        print(f"\n[ERROR] 날짜 범위 설정 오류: {e}")
        print("메뉴에서 '2. 날짜 범위 설정'을 선택하여 날짜를 설정해주세요.")
        return
    
    # 조회 실행
    execute_query(args, api_key, models, start, end)


def execute_query(
    args: argparse.Namespace,
    api_key: str,
    models: List[str],
    start: datetime,
    end: datetime
) -> None:
    """실제 조회 실행"""
    try:
        if args.verbose:
            print(f"\n[INFO] 모델 목록: {', '.join(models)}")
            start_str, end_str = date_utils.format_date_range_for_api(start, end)
            print(f"[INFO] 조회 기간: {start_str} ~ {end_str}")
        
        timezone = args.timezone or config.get_timezone()
        
        # API 클라이언트 생성
        client = api_client.FalAPIClient(api_key)
        
        # Usage API 호출
        if args.verbose:
            print("[INFO] Usage API 호출 중...")
        
        usage_data = client.get_usage(
            endpoint_ids=models,
            start=start,
            end=end,
            timeframe=args.timeframe,
            timezone=timezone,
            bound_to_timeframe=args.bound_to_timeframe,
            include_notion=args.notion
        )
        
        if args.verbose:
            print("[INFO] Usage API 호출 완료")
        
        # Pricing API 호출
        if args.verbose:
            print("[INFO] Pricing API 호출 중...")
        
        pricing_data = client.get_pricing(endpoint_ids=models)
        
        if args.verbose:
            print("[INFO] Pricing API 호출 완료")
        
        # 테이블 형식 출력
        formatter.format_for_display(usage_data, pricing_data)
        
        # Notion 저장
        if args.notion:
            if args.dry_run:
                print("\n[DRY-RUN] Notion 저장 모드 (실제 저장 안 함)")
            else:
                print("\n[INFO] Notion 저장 기능은 아직 구현되지 않았습니다.")
        
        if args.verbose:
            print("\n[SUCCESS] 작업 완료")
            
    except Exception as e:
        print(f"\n[ERROR] 조회 중 오류 발생: {e}")
        if args.verbose:
            import traceback
            traceback.print_exc()


def main():
    """메인 실행 함수"""
    try:
        # 인자 파싱
        args = parse_args()
        
        # CLI 인자가 모두 비어있으면 인터랙티브 모드
        has_cli_args = any([
            args.api_key,
            args.models,
            args.preset,
            args.start_date,
            args.end_date,
            args.timeframe,
            args.timezone,
            args.notion,
            args.verbose,
            args.dry_run
        ])
        
        if not has_cli_args:
            # 인터랙티브 모드
            interactive_mode(args)
        else:
            # CLI 모드 (기존 동작)
            cli_mode(args)
        
    except KeyboardInterrupt:
        print("\n\n프로그램을 종료합니다.")
        sys.exit(0)
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류: {e}", file=sys.stderr)
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
            date_settings = show_date_range_menu()
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
            validate_and_execute_query(args)
            input("\n계속하려면 엔터를 누르세요...")
        elif choice == 5:
            print("\n프로그램을 종료합니다.")
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
        print(f"[INFO] 모델 목록: {', '.join(models)}")
        if args.models:
            print(f"[INFO] 모델 목록이 config.json에 저장되었습니다.")
    
    # 날짜 범위 파싱
    start, end = parse_date_range(args)
    
    if args.verbose:
        start_str, end_str = date_utils.format_date_range_for_api(start, end)
        print(f"[INFO] 조회 기간: {start_str} ~ {end_str}")
    
    # 조회 실행
    execute_query(args, api_key, models, start, end)


if __name__ == "__main__":
    main()

