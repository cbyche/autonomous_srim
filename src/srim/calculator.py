import math
from datetime import datetime
from typing import Tuple, List

import numpy as np
import numpy_financial as npf


def match_tick_size(price: float) -> int:
    """한국투자증권 주식 호가 단위에 맞게 가격을 반올림한다."""
    if price >= 100000:
        return int(round(price, -3))  # 1000원 단위
    elif price >= 10000:
        return int(round(price, -2))  # 100원 단위
    else:
        return int(round(price, -1))  # 10원 단위


def calculate_price_book(b0: float, roe: float, ke: float, shares: int, discount_factor: float) -> float:
    """초과이익이 잔존한다고 가정 (ROE 감소, 무한 연도 반영)"""
    roe_rate = roe * 0.01
    ke_rate = ke * 0.01
    
    # values = B0 + B0 * (ROE - Ke) * w / (1 + Ke - w)  (w: discount_factor)
    values = b0 + b0 * (roe_rate - ke_rate) * discount_factor / (1 + ke_rate - discount_factor)
    price = values / shares
    return price


def calculate_price_lecture(b0: float, roe: float, ke: float, shares: int, discount_factor: float, pos: int) -> float:
    """ROE가 잔존한다고 가정 (10년 반영 후 현재 가치로 할인)"""
    now = datetime.now()
    
    # pos에 따라 기준년도 결정
    if pos == -1:
        years = 7
        ref_date = datetime(now.year + 2, 12, 31)
    elif pos == -2:
        years = 8
        ref_date = datetime(now.year + 1, 12, 31)
    elif pos == -3:
        years = 9
        ref_date = datetime(now.year, 12, 31)
    else:
        years = 10
        ref_date = datetime(now.year - 1, 12, 31)
        
    ke_rate = ke * 0.01
    roe_rate = roe * 0.01
    
    bt = b0
    excesses = [0.0]
    excess_rate = roe_rate - ke_rate
    
    for _ in range(years):
        excess_rate *= discount_factor
        current_roe = ke_rate + excess_rate
        excess = bt * current_roe - bt * ke_rate
        excesses.append(excess)
        bt += bt * current_roe
        
    excess_npv = npf.npv(ke_rate, excesses)
    b_value = b0 + excess_npv
    price_at_that_time = b_value / shares
    
    day_diff = (ref_date - now).days
    price = price_at_that_time / ((1 + ke_rate) ** (day_diff / 365.0))
    return price


def calculate_weighted_average(minus2: float, minus1: float, minus0: float) -> float:
    """3개년도 ROE의 가중평균 계산. (최신 연도에 높은 가중치)"""
    if minus0 >= minus1:
        if minus1 >= minus2:
            return minus0  # 지속 상승 시 최신값 사용
        else:
            return (1 * minus2 + 2 * minus1 + 3 * minus0) / 6
    else:
        if minus1 >= minus2:
            return (1 * minus2 + 2 * minus1 + 3 * minus0) / 6
        else:
            return minus0  # 지속 하락 시 최신값 사용


def calculate_srim(b0: float, roe: float, ke: float, shares: int, pos: int) -> Tuple[int, int, int, int, int]:
    """
    S-RIM 가격 5단계 산출
    반환값: (매수적정가격, 1차매도가격, 2차매도가격, 3차매도가격, 4차매도가격)
    """
    # 1. 매도가격 그룹 (할인율 1.0)
    sell_price_book = calculate_price_book(b0, roe, ke, shares, 1.0)
    sell_price_lecture = calculate_price_lecture(b0, roe, ke, shares, 1.0, pos)
    sell_target_3 = min(sell_price_book, sell_price_lecture) # 3차 매도가
    sell_target_4 = max(sell_price_book, sell_price_lecture) # 4차 매도가
    
    # 2. 적정가격 그룹 (할인율 0.9)
    proper_price_book = calculate_price_book(b0, roe, ke, shares, 0.9)
    proper_price_lecture = calculate_price_lecture(b0, roe, ke, shares, 0.9, pos)
    sell_target_1 = min(proper_price_book, proper_price_lecture) # 1차 매도가
    sell_target_2 = max(proper_price_book, proper_price_lecture) # 2차 매도가
    
    # 3. 매수가격 그룹 (할인율 0.8)
    buy_price_book = calculate_price_book(b0, roe, ke, shares, 0.8)
    buy_price_lecture = calculate_price_lecture(b0, roe, ke, shares, 0.8, pos)
    buy_target_price = min(buy_price_book, buy_price_lecture) # 매수적정가
    
    # 1차~4차 매도가격 정렬 (모델 간 간극으로 인해 순서가 뒤바뀔 수 있음)
    sell_targets = sorted([sell_target_1, sell_target_2, sell_target_3, sell_target_4])
    
    # 호가 단위 맞춤 및 최종 반환
    return (
        match_tick_size(buy_target_price),
        match_tick_size(sell_targets[0]),
        match_tick_size(sell_targets[1]),
        match_tick_size(sell_targets[2]),
        match_tick_size(sell_targets[3])
    )
