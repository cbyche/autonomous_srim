from dataclasses import dataclass
from typing import Optional

@dataclass
class SRIMResult:
    """S-RIM 분석 결과 및 종목 지표를 담는 데이터 클래스"""
    code: str
    name: str
    industry: str
    product: str
    # 가격 정보
    current_price: int
    buy_target_price: int  # 매수적정가격
    sell_target_1: int     # 1차 매도가격
    sell_target_2: int     # 2차 매도가격
    sell_target_3: int     # 3차 매도가격
    sell_target_4: int     # 4차 매도가격
    
    # 수익률
    buy_yield: float
    target_1_yield: float
    target_2_yield: float
    target_3_yield: float
    target_4_yield: float
    
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

    def is_buy_candidate(self, required_ror: float, buy_margin: float = 0.9) -> bool:
        """사용자 정의 11가지 엄격한 매수 조건을 충족하는지 여부"""
        if self.current_price <= 0:
            return False
            
        # 1. 가격 조건 (현재가 < 매수적정가격 * 0.9)
        if self.current_price >= self.buy_target_price * buy_margin:
            return False
            
        # 2. 수익성 조건 (ROE >= 요구수익률)
        if self.roe < required_ror:
            return False
            
        # 3. 현금흐름 안정성 (위험 0회 & 비율 80% 이상)
        if self.cf_risk_count > 0 or self.cf_to_op_avg < 0.8:
            return False
            
        # 4. 순이익 건전성 (4분기 합산 양수 & 적자 0회)
        if self.net_income_4q_sum <= 0 or self.net_income_deficit_count > 0:
            return False
            
        # 5. 영업이익 건전성 (4분기 합산 양수 & 적자 0회)
        if self.op_income_4q_sum <= 0 or self.op_income_deficit_count > 0:
            return False
            
        # 6. 주주환원 (배당 실시 여부)
        if self.dividend_yield <= 0 or self.dividend_payout_ratio <= 0:
            return False
            
        # 7. 지능형 업종 및 키워드 필터링
        # 이름 및 공식 업종명(Industry)에서 키워드 검사 (기업개요는 과도한 필터링 방지를 위해 제외)
        exclude_keywords = ['스팩', '리츠', '증권', '은행', '홀딩스', '지주', '건설', '화재', '종금', '캐피탈', '투자', '보험', '생명보험', '손해보험', '카드']
        exclude_exact = [
            '한국테크놀로지그룹', '인터파크', '아세아', 'CJ', 'LG', '경동인베스트', '엘브이엠씨', 
            '대웅', '아모레퍼시픽그룹', '지투알', 'BGF', '코오롱', 'GS', 'SK', '한화', 
            '현대모비스', 'DL', 'HDC', '효성', '동원개발', '금호산업', '휴온스글로벌', 
            '코오롱글로벌', '한국토지신탁', '현대해상', '계룡건설산업', '서연'
        ]
        
        # 필터링 대상 텍스트 (이름 + 공식 업종명)
        target_text = f"{self.name} {self.industry or ''}"
        
        if any(keyword in target_text for keyword in exclude_keywords):
            return False
        if self.name in exclude_exact:
            return False
            
        return True

    def should_force_sell(self, required_ror: float) -> bool:
        """기업 펀더멘털 훼손에 따른 전량 처분(강제 매도) 조건 체크"""
        
        # 1. 수익성 악화 (ROE <= Ke * 0.9)
        if self.roe <= required_ror * 0.9:
            return True
            
        # 2. 현금흐름 위험 발생 (위험 1회 이상 또는 비율 72% 미만)
        if self.cf_risk_count > 0 or self.cf_to_op_avg < (0.8 * 0.9):
            return True
            
        # 3. 순이익 적자 전환 (4분기 합산 적자 또는 분기 적자 1회 이상)
        if self.net_income_4q_sum < 0 or self.net_income_deficit_count > 0:
            return True
            
        # 4. 영업이익 적자 전환 (4분기 합산 적자 또는 분기 적자 1회 이상)
        if self.op_income_4q_sum < 0 or self.op_income_deficit_count > 0:
            return True
            
        # 5. 배당 중단 (배당수익률 또는 배당성향 0 이하)
        if self.dividend_yield <= 0 or self.dividend_payout_ratio <= 0:
            return True
            
        return False
