"""
fal.ai 사용량 추적 CLI
"""
import argparse
import sys
from typing import Optional, List
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
        모델 ID 목록
    """
    if args.models:
        # CLI에서 지정된 경우
        models = [m.strip() for m in args.models.split(",") if m.strip()]
        if models:
            # config.json에 저장
            config.save_models(models)
            return models
        else:
            raise ValueError("모델 목록이 비어있습니다.")
    else:
        # config.json에서 가져오기
        models = config.get_models()
        if not models:
            raise ValueError(
                "모델 목록이 지정되지 않았습니다. "
                "첫 실행 시 -models 옵션으로 모델 목록을 지정해주세요. "
                "예: -models fal-ai/imagen4/preview/ultra,fal-ai/nano-banana"
            )
        return models


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


def main():
    """메인 실행 함수"""
    try:
        # 인자 파싱
        args = parse_args()
        
        # API 키 가져오기
        api_key = config.get_api_key(args.api_key)
        
        # 모델 목록 가져오기
        models = get_models_from_args(args)
        
        if args.verbose:
            print(f"[INFO] 모델 목록: {', '.join(models)}")
            if args.models:
                print(f"[INFO] 모델 목록이 config.json에 저장되었습니다.")
        
        # 날짜 범위 파싱
        start, end = parse_date_range(args)
        
        if args.verbose:
            start_str, end_str = date_utils.format_date_range_for_api(start, end)
            print(f"[INFO] 조회 기간: {start_str} ~ {end_str}")
        
        # 타임존
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
        
        # Pricing API 호출 (비교용)
        if args.verbose:
            print("[INFO] Pricing API 호출 중...")
        
        pricing_data = client.get_pricing(endpoint_ids=models)
        
        if args.verbose:
            print("[INFO] Pricing API 호출 완료")
        
        # 테이블 형식 출력
        formatter.format_for_display(usage_data, pricing_data)
        
        # Notion 저장 (나중에 notion_client.py에서 구현)
        if args.notion:
            if args.dry_run:
                print("\n[DRY-RUN] Notion 저장 모드 (실제 저장 안 함)")
            else:
                print("\n[INFO] Notion 저장 기능은 아직 구현되지 않았습니다.")
        
        # 성공 메시지
        if args.verbose:
            print("\n[SUCCESS] 작업 완료")
        
    except ValueError as e:
        print(f"[ERROR] {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"[ERROR] 예상치 못한 오류: {e}", file=sys.stderr)
        if args.verbose if 'args' in locals() else False:
            import traceback
            traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

