from dataclasses import dataclass
from typing import Optional

@dataclass
class SRIMResult:
    """S-RIM 분석 결과 및 종목 지표를 담는 데이터 클래스"""
    code: str
    name: str
    industry: str
    product: str
    
    current_price: int
    buy_price: int
    proper_price: int
    sell_price: int
    last_price: int
    
    # 수익률 지표 (현재가 기준)
    buy_yield: float
    proper_yield: float
    sell_yield: float
    last_yield: float
    
    roe: float
    roe_reference: str
    
    # 추가 필터링 지표
    dividend_yield: float           # 배당수익률(%)
    dividend_payout_ratio: float    # 배당성향(%)
    cf_risk_count: int              # 현금흐름위험(회) - 영업이익(+) 영업CF(-)
    cf_to_op_avg: float             # 현금흐름/영업이익(4개년도평균)
    net_income_4q_sum: float        # 순이익(4분기누적)
    net_income_deficit_count: int   # 순이익적자(4분기횟수)
    op_income_4q_sum: float         # 영업이익(4분기누적)
    op_income_deficit_count: int    # 영업이익적자(4분기횟수)

    def is_buy_candidate(self, buy_margin: float = 0.9) -> bool:
        """이 종목이 매수 조건을 충족하는지 여부"""
        if self.current_price <= 0:
            return False
            
        # 1. 가격 조건 (현재가 < 매수가격 * margin)
        if self.current_price >= self.buy_price * buy_margin:
            return False
            
        # 2. 추가 필터링 조건
        # (향후 구체적인 필터링 로직 추가 예정)
        # 예: 현금흐름위험 2회 이상이면 제외 등
        if self.cf_risk_count >= 2:
            return False
            
        return True
