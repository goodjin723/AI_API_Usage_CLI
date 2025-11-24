"""
Google OAuth2 인증 모듈
Gmail API 접근을 위한 토큰 관리
"""
import time
import json
from pathlib import Path
from typing import Optional
import config

# Gmail API 접근 스코프
SCOPES = ['https://www.googleapis.com/auth/gmail.readonly']


def load_credentials():
    """
    credentials.json에서 CLIENT_ID와 CLIENT_SECRET 읽기
    
    Returns:
        tuple: (client_id, client_secret)
    
    Raises:
        FileNotFoundError: credentials.json 파일이 없을 때
        ValueError: credentials.json 형식이 올바르지 않을 때
    """
    credentials_path = Path(config.get_google_credentials_path())
    
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"❌ {credentials_path} 파일이 없습니다.\n"
            "Google Cloud Console에서 OAuth 클라이언트 JSON을 다운로드하세요.\n"
            "https://console.cloud.google.com/apis/credentials"
        )
    
    try:
        data = json.loads(credentials_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError as e:
        raise ValueError(f"❌ credentials.json 파일을 파싱할 수 없습니다: {e}")
    
    #  web (웹 애플리케이션) 형식 지원
    if "web" in data:
        creds = data["web"]
    else:
        raise ValueError(
            "❌ 올바른 credentials.json 형식이 아닙니다.\n"
            "'web' 형식 키가 필요합니다."
        )
    
    return creds["client_id"], creds["client_secret"]


def _load_success_html() -> str:
    """OAuth 성공 페이지 HTML 로드"""
    html_path = Path(__file__).parent / "oauth_success.html"
    
    if not html_path.exists():
        raise FileNotFoundError(
            f"OAuth 성공 페이지를 찾을 수 없습니다: {html_path}\n"
            "oauth_success.html 파일이 필요합니다."
        )
    
    return html_path.read_text(encoding='utf-8')


def get_new_tokens_via_browser() -> str:
    """
    브라우저를 통해 새로운 Access Token과 Refresh Token 발급
    (인증 완료 후 브라우저 자동 닫기 포함)
    
    Returns:
        str: 새로 발급받은 Access Token
    
    Raises:
        ImportError: google-auth-oauthlib이 설치되지 않은 경우
    """
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        import webbrowser
        import threading
        from http.server import HTTPServer, BaseHTTPRequestHandler
        from urllib.parse import urlparse, parse_qs
    except ImportError:
        raise ImportError(
            "❌ google-auth-oauthlib 패키지가 필요합니다.\n"
            "설치: pip install google-auth-oauthlib"
        )
    
    credentials_path = config.get_google_credentials_path()
    
    flow = InstalledAppFlow.from_client_secrets_file(
        credentials_path,
        SCOPES,
        redirect_uri='http://localhost:8888/'
    )
    
    # HTML 파일에서 성공 페이지 로드
    SUCCESS_HTML = _load_success_html()
    
    authorization_url, state = flow.authorization_url(
        access_type='offline',
        prompt='consent'
    )
    
    print("🌐 브라우저에서 Google 로그인 진행 중...")
    print("   - Gmail 계정 선택")
    print("   - 앱 접근 권한 허용")
    
    # 인증 결과를 저장할 변수
    auth_code = None
    server_stopped = threading.Event()
    
    class OAuthCallbackHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            nonlocal auth_code
            
            # 쿼리 파라미터에서 code 추출
            query = urlparse(self.path).query
            params = parse_qs(query)
            
            if 'code' in params:
                auth_code = params['code'][0]
                
                # 성공 페이지 전송
                self.send_response(200)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                self.wfile.write(SUCCESS_HTML.encode('utf-8'))
                
                # 서버 종료 신호
                threading.Thread(target=lambda: server_stopped.set()).start()
            else:
                # 에러 처리
                self.send_response(400)
                self.send_header('Content-type', 'text/html; charset=utf-8')
                self.end_headers()
                error_html = '<html><body><h1>인증 실패</h1><p>다시 시도해주세요.</p></body></html>'
                self.wfile.write(error_html.encode('utf-8'))
        
        def log_message(self, format, *args):
            # 로그 출력 억제
            pass
    
    # 로컬 서버 시작
    server = HTTPServer(('localhost', 8888), OAuthCallbackHandler)
    
    # 브라우저 열기
    webbrowser.open(authorization_url)
    
    # 콜백 대기 (타임아웃 5분)
    server.timeout = 300
    while not server_stopped.is_set():
        server.handle_request()
    
    if not auth_code:
        raise Exception("❌ 인증 코드를 받지 못했습니다.")
    
    # 토큰 교환
    flow.fetch_token(code=auth_code)
    creds = flow.credentials
    
    print("✅ 새 토큰 발급 완료!")
    
    save_tokens(creds.token, creds.refresh_token)
    
    return creds.token


def refresh_access_token() -> str:
    """
    Refresh Token을 사용해 새로운 Access Token 발급
    
    Returns:
        str: 갱신된 Access Token
    
    Raises:
        ImportError: google-auth 패키지가 설치되지 않은 경우
    """
    try:
        from google.oauth2.credentials import Credentials
        from google.auth.transport.requests import Request
    except ImportError:
        raise ImportError(
            "❌ google-auth 패키지가 필요합니다.\n"
            "설치: pip install google-auth"
        )
    
    tokens_path = Path(config.get_google_tokens_path())
    
    # 저장된 토큰 읽기
    if not tokens_path.exists():
        print("⚠️ 토큰 파일 없음 → 브라우저 인증 시작")
        return get_new_tokens_via_browser()
    
    try:
        data = json.loads(tokens_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        print("⚠️ 토큰 파일 손상 → 브라우저 인증 시작")
        return get_new_tokens_via_browser()
    
    refresh_token = data.get("refresh_token")
    
    if not refresh_token:
        print("⚠️ Refresh Token 없음 → 브라우저 인증 시작")
        return get_new_tokens_via_browser()
    
    # credentials.json에서 client_id, client_secret 읽기
    try:
        client_id, client_secret = load_credentials()
    except (FileNotFoundError, ValueError) as e:
        raise Exception(f"❌ Credentials 로드 실패: {e}")
    
    # Credentials 객체 생성
    creds = Credentials(
        token=data.get("access_token"),
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret
    )
    
    try:
        creds.refresh(Request())
        print("🔑 새 Access Token 발급됨")
        save_tokens(creds.token, creds.refresh_token)
        return creds.token
    except Exception as e:
        print(f"❌ 토큰 갱신 실패: {e}")
        print("→ 브라우저 인증 시작")
        return get_new_tokens_via_browser()


def save_tokens(access_token: str, refresh_token: Optional[str]) -> None:
    """
    Access Token과 Refresh Token을 파일에 저장
    
    Args:
        access_token: 액세스 토큰
        refresh_token: 리프레시 토큰 (없으면 기존 값 유지)
    """
    tokens_path = Path(config.get_google_tokens_path())
    
    # 기존 토큰 로드 (refresh_token 보존을 위해)
    existing_data = {}
    if tokens_path.exists():
        try:
            existing_data = json.loads(tokens_path.read_text(encoding='utf-8'))
        except json.JSONDecodeError:
            pass
    
    data = {
        "access_token": access_token,
        "refresh_token": refresh_token or existing_data.get("refresh_token"),
        "timestamp": time.time()
    }
    
    tokens_path.write_text(json.dumps(data, indent=2), encoding='utf-8')
    print(f"💾 토큰 저장됨: {tokens_path}")


def load_access_token() -> str:
    """
    유효한 Access Token 로드 (만료 시 자동 갱신)
    
    Returns:
        str: 유효한 Access Token
    
    Raises:
        Exception: 토큰 로드/갱신 실패 시
    """
    tokens_path = Path(config.get_google_tokens_path())
    
    if not tokens_path.exists():
        print("⚠️ 토큰 파일 없음 → 인증 시작")
        return refresh_access_token()
    
    try:
        data = json.loads(tokens_path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        print("⚠️ 토큰 파일 손상 → 인증 시작")
        return refresh_access_token()
    
    saved_time = data.get("timestamp", 0)
    
    # Access Token은 약 1시간(3600초) 유효, 안전하게 3500초로 체크
    if time.time() - saved_time > 3500:
        print("⏳ Access Token 만료 → 갱신 중...")
        return refresh_access_token()
    
    print("✔ Access Token 유효")
    return data["access_token"]


def force_reauth() -> str:
    """
    강제로 재인증 수행 (기존 토큰 삭제 후 새로 발급)
    
    Returns:
        str: 새로 발급받은 Access Token
    """
    tokens_path = Path(config.get_google_tokens_path())
    
    print("🔄 강제 재인증 시작...")
    if tokens_path.exists():
        tokens_path.unlink()
        print("   기존 토큰 삭제됨")
    
    return get_new_tokens_via_browser()


if __name__ == "__main__":
    """
    직접 실행 시 테스트 모드
    
    사용법:
        python google_auth.py           # 토큰 로드/갱신
        python google_auth.py --force   # 강제 재인증
    """
    import sys
    
    try:
        if "--force" in sys.argv:
            access_token = force_reauth()
        else:
            access_token = load_access_token()
        
        print("\n🔥 최종 Access Token:")
        print(f"   {access_token[:20]}...{access_token[-20:]}")
        print("\n✅ 인증 완료! 이 토큰을 사용하여 Gmail API에 접근할 수 있습니다.")
        
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        sys.exit(1)

