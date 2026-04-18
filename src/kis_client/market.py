import logging
import requests
from typing import Optional

from src.kis_client.auth import KISAuth

logger = logging.getLogger(__name__)

class KISMarket:
    def __init__(self, auth: KISAuth):
        self.auth = auth
        self.base_url = auth.base_url

    def get_current_price(self, code: str) -> Optional[int]:
        """주식 현재가 조회"""
        if self.auth.get_access_token() == "dummy_token":
            logger.info(f"[Mock] KIS API 현재가 조회: {code} -> 50000원")
            return 50000

        url = f"{self.base_url}/uapi/domestic-stock/v1/quotations/inquire-price"
        headers = self.auth.get_base_headers()
        headers["tr_id"] = "FHKST01010100" # 주식현재가 시세
        
        params = {
            "FID_COND_MRKT_DIV_CODE": "J",
            "FID_INPUT_ISCD": code
        }
        
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    return int(data["output"]["stck_prpr"])
            logger.error(f"Failed to get price: {res.text}")
            return None
        except Exception as e:
            logger.error(f"Exception while getting price for {code}: {e}")
            return None
