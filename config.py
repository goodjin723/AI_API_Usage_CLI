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
        "timezone": "Asia/Seoul",
        "default_date_range": {
            "preset": "last-7-days"
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
    return config.get("timezone", "Asia/Seoul")


def set_timezone(timezone: str) -> None:
    """기본 타임존 설정"""
    config = get_config()
    config["timezone"] = timezone
    save_config(config)


def save_notion_database_id(auth_method: str, database_id: str) -> None:
    """auth_method별 Notion 데이터베이스 ID 저장"""
    config = get_config()
    if "notion_databases" not in config:
        config["notion_databases"] = {}
    config["notion_databases"][auth_method] = database_id
    save_config(config)


def get_notion_database_id(auth_method: str) -> Optional[str]:
    """auth_method별 Notion 데이터베이스 ID 가져오기"""
    config = get_config()
    notion_databases = config.get("notion_databases", {})
    return notion_databases.get(auth_method)


def get_all_notion_databases() -> Dict[str, str]:
    """모든 Notion 데이터베이스 ID 가져오기"""
    config = get_config()
    return config.get("notion_databases", {})


def get_fal_ai_database_id() -> Optional[str]:
    """
    fal.ai 통합 Notion 데이터베이스 ID 가져오기
    우선순위: "fal_ai" 키 > 기존 키 중 하나 (하위 호환성)
    """
    config = get_config()
    notion_databases = config.get("notion_databases", {})
    
    # "fal_ai" 키가 있으면 우선 사용
    if "fal_ai" in notion_databases:
        return notion_databases["fal_ai"]
    
    # 하위 호환성: 기존 키 중 하나라도 있으면 첫 번째 것 사용
    # (invoice 제외)
    for key, db_id in notion_databases.items():
        if key != "invoice" and not key.startswith("invoice_"):
            return db_id
    
    return None


def save_fal_ai_database_id(database_id: str) -> None:
    """fal.ai 통합 Notion 데이터베이스 ID 저장"""
    save_notion_database_id("fal_ai", database_id)


def get_notion_api_key(cli_notion_api_key: Optional[str] = None) -> Optional[str]:
    """
    Notion API 키 가져오기
    우선순위: CLI 옵션 > config.json > 환경 변수 > None
    """
    if cli_notion_api_key:
        return cli_notion_api_key
    
    config_data = get_config()
    notion_api_key = config_data.get("notion_api_key")
    if notion_api_key:
        return notion_api_key
    
    return os.getenv("NOTION_API_KEY")


def save_notion_api_key(api_key: str) -> None:
    """Notion API 키를 config.json에 저장"""
    config_data = get_config()
    config_data["notion_api_key"] = api_key
    save_config(config_data)


def get_openai_api_key(cli_openai_api_key: Optional[str] = None) -> Optional[str]:
    """
    OpenAI API 키 가져오기
    우선순위: CLI 옵션 > 환경 변수 > config.json > None
    """
    if cli_openai_api_key:
        return cli_openai_api_key
    
    # 환경 변수 우선
    env_key = os.getenv("OPENAI_API_KEY")
    if env_key:
        return env_key
    
    # config.json에서 가져오기
    config_data = get_config()
    return config_data.get("openai_api_key")


def save_openai_api_key(api_key: str) -> None:
    """OpenAI API 키를 config.json에 저장"""
    config_data = get_config()
    config_data["openai_api_key"] = api_key
    save_config(config_data)


def get_google_credentials_path() -> str:
    """
    Google OAuth credentials.json 파일 경로 가져오기
    우선순위: config.json > 기본 경로 (./credentials.json)
    """
    config_data = get_config()
    path = config_data.get("google_credentials_path", "./credentials.json")
    return str(PROJECT_ROOT / path) if not os.path.isabs(path) else path


def get_google_tokens_path() -> str:
    """
    Google OAuth tokens.json 파일 경로 가져오기
    우선순위: config.json > 기본 경로 (./google_tokens.json)
    """
    config_data = get_config()
    path = config_data.get("google_tokens_path", "./google_tokens.json")
    return str(PROJECT_ROOT / path) if not os.path.isabs(path) else path


def save_google_paths(credentials_path: str, tokens_path: str) -> None:
    """Google OAuth 파일 경로를 config.json에 저장"""
    config_data = get_config()
    config_data["google_credentials_path"] = credentials_path
    config_data["google_tokens_path"] = tokens_path
    save_config(config_data)


def get_invoice_search_keywords() -> List[str]:
    """
    Gmail invoice 검색 키워드 가져오기 (리스트)
    우선순위: config.json > 기본값 (Replit)
    
    Returns:
        List[str]: 검색 키워드 리스트
    """
    config_data = get_config()
    keywords = config_data.get("invoice_search_keywords", ["Your Replit receipt"])
    
    # 하위 호환성: 문자열이면 리스트로 변환
    if isinstance(keywords, str):
        return [keywords]
    
    # 리스트가 아니거나 비어있으면 기본값
    if not isinstance(keywords, list) or not keywords:
        return ["Your Replit receipt"]
    
    return keywords


def save_invoice_search_keywords(keywords: List[str]) -> None:
    """
    Gmail invoice 검색 키워드를 config.json에 저장
    
    Args:
        keywords: 검색 키워드 리스트
    """
    config_data = get_config()
    config_data["invoice_search_keywords"] = keywords
    save_config(config_data)


# 모듈 로드 시 환경 변수 자동 로딩
load_env()

