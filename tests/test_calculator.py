import pytest
import numpy as np

from src.srim.calculator import (
    match_tick_size,
    calculate_price_book,
    calculate_price_lecture,
    calculate_weighted_average,
    calculate_srim
)

def test_match_tick_size():
    assert match_tick_size(152300) == 152000
    assert match_tick_size(152600) == 153000
    assert match_tick_size(45230) == 45200
    assert match_tick_size(45260) == 45300
    assert match_tick_size(3214) == 3210
    assert match_tick_size(3216) == 3220

def test_calculate_weighted_average():
    # 상승 패턴: minus0 >= minus1 >= minus2 -> minus0 반환
    assert calculate_weighted_average(10.0, 15.0, 20.0) == 20.0
    # 하락 패턴: minus0 < minus1 < minus2 -> minus0 반환
    assert calculate_weighted_average(20.0, 15.0, 10.0) == 10.0
    # 혼합 패턴 1: minus0 >= minus1, minus1 < minus2 -> 가중평균
    # (1*20 + 2*10 + 3*15) / 6 = (20 + 20 + 45) / 6 = 85 / 6 = 14.166...
    assert np.isclose(calculate_weighted_average(20.0, 10.0, 15.0), 85.0/6.0)
    # 혼합 패턴 2: minus0 < minus1, minus1 >= minus2 -> 가중평균
    # (1*10 + 2*20 + 3*15) / 6 = (10 + 40 + 45) / 6 = 95 / 6 = 15.833...
    assert np.isclose(calculate_weighted_average(10.0, 20.0, 15.0), 95.0/6.0)

def test_calculate_price_book():
    b0 = 100000000  # 1억
    roe = 15.0      # 15%
    ke = 8.0        # 8%
    shares = 10000  # 1만 주
    discount_factor = 1.0
    
    # values = B0 + B0*(roe-ke)*w / (1+ke-w)
    # values = 1억 + 1억*(0.07)*1.0 / (1.08-1.0) = 1억 + 700만/0.08 = 1억 + 8750만 = 1억8750만
    # price = 1억8750만 / 1만 = 18750
    price = calculate_price_book(b0, roe, ke, shares, discount_factor)
    assert np.isclose(price, 18750.0)

def test_calculate_srim():
    b0 = 100000000
    roe = 15.0
    ke = 8.0
    shares = 10000
    pos = -1
    
    buy_p, s1, s2, s3, s4 = calculate_srim(b0, roe, ke, shares, pos)
    
    # 모든 가격은 int형이며 호가 단위에 맞춰져 있어야 함
    assert isinstance(buy_p, int)
    assert isinstance(s1, int)
    assert isinstance(s2, int)
    assert isinstance(s3, int)
    assert isinstance(s4, int)
    assert buy_p <= s1 <= s2 <= s3 <= s4
