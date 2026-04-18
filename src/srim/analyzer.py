import math
import logging
from typing import Tuple, Optional, List

import pandas as pd

from src.srim.models import SRIMResult
from src.srim.calculator import calculate_weighted_average, calculate_srim
from src.srim.data_fetcher import parse_fnguide

logger = logging.getLogger(__name__)


def calculate_roe_b0(fh: pd.DataFrame) -> Tuple[bool, str, float, str, float, int]:
    """
    재무 하이라이트(fh) 데이터에서 적정 ROE와 B0(지배주주지분)를 산출한다.
    반환값: (성공여부, 메시지, 선택된ROE, ROE기준년도, B0, pos)
    """
    try:
        roe = fh.loc['ROE', :]
        b0 = fh.loc['지배주주지분', :]
        pos = 0
        
        # +2year(E)
        if not math.isnan(roe.iloc[-1]) and not math.isnan(b0.iloc[-1]):
            selected_roe = float(roe.iloc[-1])
            roe_ref = str(roe.index[-1])
            selected_b0 = float(b0.iloc[-1]) * (10**8) # 억 단위 변환
            pos = -1
        # +1year(E)
        elif not math.isnan(roe.iloc[-2]) and not math.isnan(b0.iloc[-2]):
            selected_roe = float(roe.iloc[-2])
            roe_ref = str(roe.index[-2])
            selected_b0 = float(b0.iloc[-2]) * (10**8)
            pos = -2
        # 0year(E) - weighted average
        elif not roe.iloc[-5:-2].isnull().values.any() and not math.isnan(b0.iloc[-3]):
            extracted_roe = roe.iloc[-5:-2].astype(float)
            selected_roe = calculate_weighted_average(extracted_roe.iloc[0], extracted_roe.iloc[1], extracted_roe.iloc[2])
            roe_ref = str(roe.index[-3])
            selected_b0 = float(b0.iloc[-3]) * (10**8)
            pos = -3
        # -1year - weighted average
        elif not roe.iloc[-6:-3].isnull().values.any() and not math.isnan(float(b0.iloc[-4])):
            extracted_roe = roe.iloc[-6:-3].astype(float)
            selected_roe = calculate_weighted_average(extracted_roe.iloc[0], extracted_roe.iloc[1], extracted_roe.iloc[2])
            roe_ref = str(roe.index[-4])
            selected_b0 = float(b0.iloc[-4]) * (10**8)
            pos = -4
        else:
            return False, 'not enough ROE history', 0.0, '', 0.0, 0
            
        return True, '', selected_roe, roe_ref, selected_b0, pos
    except Exception as e:
        return False, str(e), 0.0, '', 0.0, 0


def analyze_stock(code: str, name: str, industry: str, product: str, required_ror: float) -> Optional[SRIMResult]:
    """
    단일 종목에 대해 S-RIM 분석을 수행한다.
    """
    status, msg, data = parse_fnguide(code)
    if not status:
        logger.warning(f"[{code}] {name} 파싱 실패: {msg}")
        return None
        
    current_price = data['current_price']
    shares = data['shares']
    fh = data['fh']
    fh_quater = data['fh_quater']
    fs = data['fs']
    
    # ROE 및 B0 산출
    status, msg, roe, roe_ref, b0, pos = calculate_roe_b0(fh)
    if not status:
        logger.warning(f"[{code}] {name} ROE 계산 실패: {msg}")
        return None
        
    # S-RIM 가격 4단계 산출
    try:
        buy_price, proper_price, sell_price, last_price = calculate_srim(b0, roe, required_ror, shares, pos)
    except Exception as e:
        logger.warning(f"[{code}] {name} S-RIM 계산 실패: {e}")
        return None
        
    # 결과 객체 생성
    try:
        dividend_yield = float(fh.loc['배당수익률'].iloc[-4])
        if math.isnan(dividend_yield): dividend_yield = 0.0
    except: dividend_yield = 0.0
    
    try:
        dividend_payout = float(fh.loc['배당성향(%)'].iloc[-4])
        if math.isnan(dividend_payout): dividend_payout = 0.0
    except: dividend_payout = 0.0
    
    try:
        cf_risk_count = int(pd.DataFrame(fs.loc['CF이익검토']).sum().iloc[0])
    except: cf_risk_count = 0
    
    try:
        cf_to_op_avg = float(fs.loc['CF이익비율'].mean())
    except: cf_to_op_avg = 0.0
    
    try:
        net_income_4q_sum = float(fh_quater.loc['지배주주순이익'].astype(float).sum())
        net_income_def_count = int(pd.DataFrame(fh_quater.loc['지배주주순이익'].astype(float) < 0).sum().iloc[0])
        op_income_4q_sum = float(fh_quater.loc['영업이익'].astype(float).sum())
        op_income_def_count = int(pd.DataFrame(fh_quater.loc['영업이익'].astype(float) < 0).sum().iloc[0])
    except:
        net_income_4q_sum = 0.0
        net_income_def_count = 0
        op_income_4q_sum = 0.0
        op_income_def_count = 0

    return SRIMResult(
        code=code,
        name=name,
        industry=industry,
        product=product,
        current_price=current_price,
        buy_price=buy_price,
        proper_price=proper_price,
        sell_price=sell_price,
        last_price=last_price,
        buy_yield=round((buy_price - current_price) / current_price * 100, 2) if current_price else 0,
        proper_yield=round((proper_price - current_price) / current_price * 100, 2) if current_price else 0,
        sell_yield=round((sell_price - current_price) / current_price * 100, 2) if current_price else 0,
        last_yield=round((last_price - current_price) / current_price * 100, 2) if current_price else 0,
        roe=round(roe, 2),
        roe_reference=roe_ref,
        dividend_yield=dividend_yield,
        dividend_payout_ratio=round(dividend_payout, 2),
        cf_risk_count=cf_risk_count,
        cf_to_op_avg=round(cf_to_op_avg, 2),
        net_income_4q_sum=net_income_4q_sum,
        net_income_deficit_count=net_income_def_count,
        op_income_4q_sum=op_income_4q_sum,
        op_income_deficit_count=op_income_def_count
    )
