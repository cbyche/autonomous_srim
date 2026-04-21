import logging
import requests
from typing import Optional, Dict

from src.kis_client.auth import KISAuth
from src.config import get_config_value

logger = logging.getLogger(__name__)

class KISAccount:
    def __init__(self, auth: KISAuth, config: dict):
        self.auth = auth
        self.base_url = auth.base_url
        self.account_no = get_config_value(config, "kis_api", "account_no")
        self.is_mock = get_config_value(config, "trading", "is_mock", default=True)

    def _split_account(self) -> tuple:
        if not self.account_no or len(self.account_no) < 10:
            return "00000000", "01"
        return self.account_no[:8], self.account_no[8:10]

    def place_order(self, code: str, qty: int, price: int, order_type: str) -> bool:
        """
        주식 매수/매도 주문. order_type은 'BUY' 또는 'SELL'
        """
        if self.auth.get_access_token() == "dummy_token" or self.is_mock:
            logger.info(f"[Mock] KIS API {order_type} 주문: {code} {qty}주 @ {price}원")
            return True

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/order-cash"
        headers = self.auth.get_base_headers()
        
        # 실전투자/모의투자 여부에 따른 TR_ID (모의투자는 V, 실전은 T)
        prefix = "V" if "vps" in self.base_url else "T"
        headers["tr_id"] = f"{prefix}TCA0608U" if order_type == "SELL" else f"{prefix}TCA0608U" # 매수/매도 TR ID 분기 필요, 단순화
        # 실제 TR_ID: 매수 TTCA0802U / 매도 TTCA0801U (실전), VTTC0802U / VTTC0801U (모의)
        if order_type == "BUY":
            headers["tr_id"] = "VTTC0802U" if "vps" in self.base_url else "TTCA0802U"
        else:
            headers["tr_id"] = "VTTC0801U" if "vps" in self.base_url else "TTCA0801U"

        cano, prdt_abrv_name = self._split_account()
        
        body = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt_abrv_name,
            "PDNO": code,
            "ORD_DVSN": "00", # 지정가
            "ORD_QTY": str(qty),
            "ORD_UNPR": str(price)
        }
        
        try:
            res = requests.post(url, headers=headers, json=body, timeout=10)
            data = res.json()
            if res.status_code == 200 and data.get("rt_cd") == "0":
                logger.info(f"주문 성공: {data.get('msg1')}")
                return True
            else:
                logger.error(f"주문 실패: {data}")
                return False
        except Exception as e:
            logger.error(f"주문 예외 발생: {e}")
            return False

    def get_balance(self) -> Optional[Dict[str, dict]]:
        """
        계좌 잔고를 조회하여 {종목코드: {'qty': 수량, 'avg_price': 평단가}} 형태로 반환한다.
        - 빈 계좌인 경우 빈 딕셔너리 {} 반환
        - API 호출 실패 또는 Mock 모드인 경우 None 반환
        """
        if self.auth.get_access_token() == "dummy_token" or self.is_mock:
            # Mock 모드에서는 None 반환
            return None

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-balance"
        headers = self.auth.get_base_headers()
        
        prefix = "V" if "vps" in self.base_url else "T"
        headers["tr_id"] = f"{prefix}TTC8434R"
        
        cano, prdt_abrv_name = self._split_account()
        
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt_abrv_name,
            "AFHR_FLPR_YN": "N",
            "OFL_YN": "",
            "INQR_DVSN": "02",
            "UNPR_DVSN": "01",
            "FUND_STTL_ICLD_YN": "N",
            "FNCG_AMT_AUTO_RDPT_YN": "N",
            "PRCS_DVSN": "00",
            "CTX_AREA_FK100": "",
            "CTX_AREA_NK100": ""
        }
        
        balance_dict = {}
        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    for item in data.get("output1", []):
                        qty = int(item.get("hldg_qty", 0))
                        if qty > 0:
                            code = item.get("pdno")
                            avg_price = float(item.get("pchs_avg_pric", 0))
                            balance_dict[code] = {
                                "qty": qty,
                                "avg_price": int(avg_price)
                            }
                    return balance_dict
            logger.error(f"잔고 조회 실패: {res.text}")
            return None
        except Exception as e:
            logger.error(f"잔고 조회 예외 발생: {e}")
            return None

    def get_available_cash(self) -> int:
        """
        주문 가능 현금(예수금) 조회.
        - Mock 모드에서는 설정된 기본 투자금액을 반환한다.
        - 실전에서는 KIS inquire-psbl-order API를 호출하여 실제 주문 가능 금액을 반환한다.
        """
        if self.auth.get_access_token() == "dummy_token" or self.is_mock:
            logger.info("[Mock] 주문 가능 현금 조회 → 기본값 5,000,000원 반환")
            return 5_000_000

        url = f"{self.base_url}/uapi/domestic-stock/v1/trading/inquire-psbl-order"
        headers = self.auth.get_base_headers()
        prefix = "V" if "vps" in self.base_url else "T"
        headers["tr_id"] = f"{prefix}TTC8908R"

        cano, prdt_abrv_name = self._split_account()
        params = {
            "CANO": cano,
            "ACNT_PRDT_CD": prdt_abrv_name,
            "PDNO": "005930",   # 종목코드는 임의값 (예수금 조회 목적)
            "ORD_UNPR": "0",
            "ORD_DVSN": "01",
            "CMA_EVLU_AMT_ICLD_YN": "N",
            "OVRS_ICLD_YN": "N"
        }

        try:
            res = requests.get(url, headers=headers, params=params, timeout=10)
            if res.status_code == 200:
                data = res.json()
                if data.get("rt_cd") == "0":
                    # nrcvb_buy_amt: 미수 없이 살 수 있는 현금 금액
                    cash = int(data["output"].get("nrcvb_buy_amt", 0))
                    logger.info(f"주문 가능 현금 조회 완료: {cash:,}원")
                    return cash
            logger.error(f"주문 가능 현금 조회 실패: {res.text}")
            return 0
        except Exception as e:
            logger.error(f"주문 가능 현금 조회 예외: {e}")
            return 0
