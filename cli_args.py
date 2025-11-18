"""
CLI 인자 파싱 모듈
argparse를 사용한 명령줄 인자 정의 및 파싱
"""
import argparse
import config


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
        help="실제 저장 없이 미리보기만 (Notion 저장 시)"
    )

    parser.add_argument(
        "-update-existing",
        action="store_true",
        help="Notion에 중복 데이터가 있으면 업데이트 (기본값: 중복 시 스킵)"
    )

    return parser.parse_args()
