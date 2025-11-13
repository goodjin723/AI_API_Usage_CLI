"""
날짜/타임존 처리 유틸리티
ISO8601 형식 변환, preset 처리, 타임존 변환
"""
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from zoneinfo import ZoneInfo
import config


def parse_date(date_str: str, tz: Optional[str] = None) -> datetime:
    """
    날짜 문자열을 datetime 객체로 변환
    지원 형식: YYYY-MM-DD, YYYY-MM-DDTHH:MM:SS, ISO8601
    
    Args:
        date_str: 날짜 문자열
        tz: 타임존 (기본값: config에서 가져옴)
    
    Returns:
        datetime 객체 (타임존 정보 포함)
    """
    if not tz:
        tz = config.get_timezone()
    
    # 타임존 객체 생성
    timezone_obj = ZoneInfo(tz) if tz else timezone.utc
    
    # ISO8601 형식 시도 (예: 2025-01-01T00:00:00Z 또는 2025-01-01T00:00:00+09:00)
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone_obj)
        return dt
    except ValueError:
        pass
    
    # YYYY-MM-DD 형식 시도
    try:
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        # 타임존이 없으면 지정된 타임존으로 설정
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone_obj)
        return dt
    except ValueError:
        pass
    
    raise ValueError(f"날짜 형식이 올바르지 않습니다: {date_str}")


def to_iso8601(dt: datetime, include_time: bool = True) -> str:
    """
    datetime 객체를 ISO8601 형식 문자열로 변환
    
    Args:
        dt: datetime 객체
        include_time: 시간 포함 여부 (False면 날짜만)
    
    Returns:
        ISO8601 형식 문자열
    """
    # UTC로 변환
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    
    if include_time:
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    else:
        return dt.strftime("%Y-%m-%d")


def get_preset_range(preset: str, tz: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    preset 옵션에 따른 날짜 범위 반환
    
    Args:
        preset: preset 이름 (today, yesterday, last-7-days, last-30-days, this-month)
        tz: 타임존 (기본값: config에서 가져옴)
    
    Returns:
        (시작 날짜, 종료 날짜) 튜플
    """
    if not tz:
        tz = config.get_timezone()
    
    timezone_obj = ZoneInfo(tz) if tz else timezone.utc
    now = datetime.now(timezone_obj)
    
    if preset == "today":
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif preset == "yesterday":
        yesterday = now - timedelta(days=1)
        start = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        end = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
    elif preset == "last-7-days":
        start = (now - timedelta(days=7)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif preset == "last-30-days":
        start = (now - timedelta(days=30)).replace(hour=0, minute=0, second=0, microsecond=0)
        end = now
    elif preset == "this-month":
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = now
    else:
        raise ValueError(f"알 수 없는 preset: {preset}")
    
    return start, end


def get_default_date_range(tz: Optional[str] = None) -> Tuple[datetime, datetime]:
    """
    기본 날짜 범위 반환 (24시간 전부터 현재까지)
    
    Args:
        tz: 타임존 (기본값: config에서 가져옴)
    
    Returns:
        (시작 날짜, 종료 날짜) 튜플
    """
    if not tz:
        tz = config.get_timezone()
    
    timezone_obj = ZoneInfo(tz) if tz else timezone.utc
    now = datetime.now(timezone_obj)
    start = now - timedelta(hours=24)
    
    return start, now


def parse_date_range(
    preset: Optional[str] = None,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    tz: Optional[str] = None
) -> Tuple[datetime, datetime]:
    """
    날짜 범위 파싱 (preset 또는 start_date/end_date)
    
    Args:
        preset: preset 이름 (today, yesterday, last-7-days, last-30-days, this-month)
        start_date: 시작 날짜 문자열
        end_date: 종료 날짜 문자열
        tz: 타임존 (기본값: config에서 가져옴)
    
    Returns:
        (시작 날짜, 종료 날짜) 튜플 (ISO8601 형식 문자열)
    """
    if not tz:
        tz = config.get_timezone()
    
    # preset 우선 처리
    if preset:
        start, end = get_preset_range(preset, tz)
    elif start_date:
        start = parse_date(start_date, tz)
        if end_date:
            end = parse_date(end_date, tz)
        else:
            # end_date가 없으면 현재 시간
            timezone_obj = ZoneInfo(tz) if tz else timezone.utc
            end = datetime.now(timezone_obj)
    else:
        # 둘 다 없으면 기본값 (24시간 전부터 현재까지)
        start, end = get_default_date_range(tz)
    
    # 종료 날짜가 시작 날짜보다 이전이면 에러
    if end < start:
        raise ValueError("종료 날짜가 시작 날짜보다 이전일 수 없습니다.")
    
    return start, end


def convert_to_utc(dt: datetime) -> datetime:
    """
    datetime을 UTC로 변환
    
    Args:
        dt: datetime 객체
    
    Returns:
        UTC로 변환된 datetime 객체
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def format_date_range_for_api(
    start: datetime,
    end: datetime,
    include_time: bool = True
) -> Tuple[str, str]:
    """
    API 호출용 날짜 범위 포맷팅 (ISO8601 형식)
    
    Args:
        start: 시작 datetime
        end: 종료 datetime
        include_time: 시간 포함 여부
    
    Returns:
        (시작 날짜 문자열, 종료 날짜 문자열) 튜플
    """
    start_utc = convert_to_utc(start)
    end_utc = convert_to_utc(end)
    
    return to_iso8601(start_utc, include_time), to_iso8601(end_utc, include_time)

