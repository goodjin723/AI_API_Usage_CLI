"""
설정 관리 모듈
환경 변수 로딩 및 config.json 파일 관리
"""
import os
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

try:
    from dotenv import load_dotenv  # type: ignore
except ImportError:
    load_dotenv = None  # type: ignore


# 프로젝트 루트 디렉토리
PROJECT_ROOT = Path(__file__).parent
CONFIG_FILE = PROJECT_ROOT / "config.json"
ENV_FILE = PROJECT_ROOT / ".env"


def load_env() -> None:
    """환경 변수 로딩 (.env 파일 지원)"""
    if load_dotenv:
        if ENV_FILE.exists():
            load_dotenv(ENV_FILE)
        else:
            # .env 파일이 없어도 환경 변수는 로드 가능
            load_dotenv(override=False)


def get_config() -> Dict[str, Any]:
    """config.json 파일 로드"""
    if CONFIG_FILE.exists():
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            # 파일이 손상되었거나 읽을 수 없으면 기본값 반환
            return _get_default_config()
    return _get_default_config()


def save_config(config: Dict[str, Any]) -> None:
    """config.json 파일 저장"""
    try:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
    except IOError as e:
        raise IOError(f"설정 파일 저장 실패: {e}")


def _get_default_config() -> Dict[str, Any]:
    """기본 설정값"""
    return {
        "timezone": "GMT",
        "default_date_range": {
            "preset": "last-30-days"
        },
        "models": []
    }


def get_api_key(cli_api_key: Optional[str] = None) -> Optional[str]:
    """
    fal.ai Admin API 키 가져오기
    우선순위: CLI 옵션 > config.json > 환경 변수 > None
    """
    if cli_api_key:
        return cli_api_key
    
    config = get_config()
    api_key = config.get("api_key")
    if api_key:
        return api_key
    
    api_key = os.getenv("FAL_ADMIN_API_KEY")
    return api_key


def save_api_key(api_key: str) -> None:
    """API 키를 config.json에 저장"""
    config = get_config()
    config["api_key"] = api_key
    save_config(config)

def save_models(models: List[str]) -> None:
    """모델 목록을 config.json에 저장"""
    config = get_config()
    config["models"] = models
    save_config(config)


def get_models() -> List[str]:
    """config.json에서 모델 목록 가져오기"""
    config = get_config()
    return config.get("models", [])


def get_timezone() -> str:
    """기본 타임존 가져오기"""
    config = get_config()
    return config.get("timezone", "GMT")


def set_timezone(timezone: str) -> None:
    """기본 타임존 설정"""
    config = get_config()
    config["timezone"] = timezone
    save_config(config)


# 모듈 로드 시 환경 변수 자동 로딩
load_env()

