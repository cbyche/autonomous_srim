import logging
import requests
import time
from typing import Optional

from src.config import get_config_value

logger = logging.getLogger(__name__)

class KISAuth:
    def __init__(self, config: dict):
        self.config = config
        self.base_url = get_config_value(config, "kis_api", "base_url")
        self.app_key = get_config_value(config, "kis_api", "app_key")
        self.app_secret = get_config_value(config, "kis_api", "app_secret")
        
        self.access_token: Optional[str] = None
        self.token_expired_at: float = 0

    def get_access_token(self) -> str:
        """액세스 토큰을 발급받거나 캐시된 토큰을 반환한다."""
        if not self.app_key or not self.app_secret:
            logger.warning("KIS API Key/Secret is not configured. Using dummy token.")
            return "dummy_token"

        # 토큰 유효기간 확인 (보통 24시간, 1시간 전 갱신)
        if self.access_token and time.time() < self.token_expired_at:
            return self.access_token

        url = f"{self.base_url}/oauth2/tokenP"
        headers = {"content-type": "application/json"}
        body = {
            "grant_type": "client_credentials",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }

        try:
            res = requests.post(url, headers=headers, json=body, timeout=10)
            if res.status_code == 200:
                data = res.json()
                self.access_token = data.get("access_token")
                expires_in = int(data.get("expires_in", 86400))
                self.token_expired_at = time.time() + expires_in - 3600 # 1시간 여유
                logger.info("KIS API Access Token issued successfully.")
                return self.access_token
            else:
                logger.error(f"Failed to get KIS token: {res.text}")
                return "dummy_token"
        except Exception as e:
            logger.error(f"Exception while getting KIS token: {e}")
            return "dummy_token"

    def get_base_headers(self) -> dict:
        token = self.get_access_token()
        return {
            "content-type": "application/json",
            "authorization": f"Bearer {token}",
            "appkey": self.app_key,
            "appsecret": self.app_secret
        }
