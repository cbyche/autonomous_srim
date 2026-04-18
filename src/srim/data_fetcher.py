import math
import logging
import random
import time
from typing import Tuple, Optional

import pandas as pd
import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)

# 브라우저 위장을 위한 User-Agent 리스트
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/119.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
]

# 요청 간 최소 간격 유지를 위한 전역 변수
_last_request_time = 0.0

def _get_safe_session() -> requests.Session:
    """랜덤 헤더가 설정된 세션 반환"""
    session = requests.Session()
    session.headers.update({
        "User-Agent": random.choice(USER_AGENTS),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Referer": "http://comp.fnguide.com/",
    })
    return session

def _wait_for_rate_limit(min_gap: float = 0.5, max_gap: float = 1.5):
    """요청 간 랜덤 지연 추가"""
    global _last_request_time
    now = time.time()
    elapsed = now - _last_request_time
    
    # 설정된 최소 간격보다 빨리 요청이 들어오면 대기
    wait_time = random.uniform(min_gap, max_gap)
    if elapsed < wait_time:
        time.sleep(wait_time - elapsed)
        
    _last_request_time = time.time()

def get_krx_list() -> pd.DataFrame:
    """KRX 상장법인목록 다운로드"""
    try:
        krx_df = pd.read_html('http://kind.krx.co.kr/corpgeneral/corpList.do?method=download&searchType=13', header=0)[0]
        krx_df['종목코드'] = krx_df['종목코드'].astype(str).str.zfill(6)
        krx_df = krx_df[['종목코드', '회사명', '업종', '주요제품']]
        krx_df = krx_df.rename(columns={'종목코드': 'code', '회사명': 'name', '업종': 'industry', '주요제품': 'product'})
        return krx_df
    except Exception as e:
        logger.error(f"KRX 종목 리스트 수집 실패: {e}")
        return pd.DataFrame()


def get_required_rate_of_return() -> float:
    """KIS Rating에서 BBB- 5년물 회사채 수익률 조회"""
    try:
        bond_ror_df = pd.read_html('https://www.kisrating.com/ratingsStatistics/statics_spread.do')[0]
        bond_ror_df = bond_ror_df.set_index(['구분'])
        required_ror_bbb_minus = bond_ror_df.loc['BBB-']
        # 5년물 수익률 반환
        return float(required_ror_bbb_minus.loc['5년'])
    except Exception as e:
        logger.error(f"회사채 수익률 수집 실패: {e}")
        # 실패 시 기본값 (예: 8.0%) 반환
        return 8.0


def parse_fnguide(code: str) -> Tuple[bool, str, dict]:
    """
    FnGuide에서 종목의 재무 데이터를 파싱한다.
    반환값: (성공여부, 메시지, 파싱된데이터_dict)
    """
    url_main = f'http://comp.fnguide.com/SVO2/asp/SVD_Main.asp?pGB=1&gicode=A{code}&cID=&MenuYn=Y&ReportGB=D&NewMenuID=101&stkGb=701'
    url_finance = f'http://comp.fnguide.com/SVO2/asp/SVD_Finance.asp?pGB=1&gicode=A{code}&cID=&MenuYn=Y&ReportGB=D&NewMenuID=103&stkGb=701'
    
    result = {}
    session = _get_safe_session()
    
    try:
        # 1. Main 페이지 파싱
        _wait_for_rate_limit()
        resp = session.get(url_main, timeout=10)
        soup = BeautifulSoup(resp.content, 'html.parser')
        html_snapshot = soup.find('body')
        tables = pd.read_html(str(html_snapshot.find_all('table')))
        
        # 업종 및 기업개요 추출 (지능형 필터링용)
        try:
            # WICS 업종 추출
            stk_group = soup.find('em', class_='stk_group')
            result['industry'] = stk_group.text.replace('WICS 업종 :', '').strip() if stk_group else ""
            
            # 기업개요 추출
            um_txt = soup.find('div', class_='um_txt')
            result['product'] = um_txt.text.strip() if um_txt else ""
        except:
            result['industry'] = ""
            result['product'] = ""

        # 현재가 & 발행주식수
        cs = tables[0]
        result['current_price'] = int(cs.iloc[0, 1].split('/')[0].replace(',', ''))
        
        shares_str = cs.iloc[6, 1].replace(',', '').split('/')
        shares = int(shares_str[0]) + int(shares_str[1])
        
        # 주주구분현황 (자기주식)
        sh = tables[4]
        own_shares = sh.iloc[4, 2]
        if math.isnan(own_shares):
            own_shares = 0
        else:
            own_shares = int(own_shares)
            
        result['shares'] = shares - own_shares
        
        # Financial Highlight (연간)
        fh = tables[11]
        fh.columns = fh.columns.droplevel()
        if 'IFRS(연결)' in fh:
            accounting = 'IFRS(연결)'
        elif 'GAAP(연결)' in fh:
            accounting = 'GAAP(연결)'
        else:
            return False, 'Neither IFRS(연결) nor GAAP(연결)', {}
            
        fh.index = fh[accounting].values
        fh = fh.drop([accounting], axis=1)
        
        fh = fh.loc[['지배주주지분', 'ROE', 'EPS(원)', 'DPS(원)', 'BPS(원)', '배당수익률'], :]
        fh = fh.rename(index={'DPS(원)': 'DPS', 'BPS(원)': 'BPS', 'EPS(원)': 'EPS'})
        fh.loc['DPS'] = fh.loc['DPS'].fillna(0)
        
        temp_df = pd.DataFrame({'배당성향(%)': fh.loc['DPS'].astype(float) / fh.loc['EPS'].astype(float) * 100}).T
        fh = pd.concat([fh, temp_df])
        result['fh'] = fh
        
        # Financial Highlight (분기)
        fh_quater = tables[12]
        fh_quater.columns = fh_quater.columns.droplevel()
        if 'IFRS(연결)' in fh_quater:
            accounting = 'IFRS(연결)'
        elif 'GAAP(연결)' in fh_quater:
            accounting = 'GAAP(연결)'
        else:
            return False, 'Neither IFRS(연결) nor GAAP(연결) in quarterly', {}
            
        fh_quater.index = fh_quater[accounting].values
        fh_quater = fh_quater.drop([accounting], axis=1)
        fh_quater = fh_quater.loc[['지배주주순이익', '영업이익'], :].fillna(0)
        # 보통 최근 4분기를 선택하는 로직 (index 1, 2, 3, 4) - 레거시 로직 유지
        try:
            fh_quater = fh_quater.iloc[:, [1, 2, 3, 4]]
        except IndexError:
            pass # 열이 부족한 경우 예외 처리
        result['fh_quater'] = fh_quater
        
        # 2. Finance 페이지 파싱
        _wait_for_rate_limit()
        resp2 = session.get(url_finance, timeout=10)
        html_fs = BeautifulSoup(resp2.content, 'html.parser').find('body')
        tables2 = pd.read_html(str(html_fs.find_all('table')))
        
        # 포괄손익계산서
        ci = tables2[0]
        ci.iloc[:, 0] = ci.iloc[:, 0].str.replace('계산에 참여한 계정 펼치기', '')
        if 'IFRS(연결)' in ci:
            accounting = 'IFRS(연결)'
        elif 'GAAP(연결)' in ci:
            accounting = 'GAAP(연결)'
        else:
            return False, 'Neither IFRS(연결) or GAAP(연결) in FS', {}
            
        ci.index = ci[accounting].values
        
        # '전년동기', '전년동기(%)' 컬럼이 있으면 삭제
        cols_to_drop = [accounting]
        for c in ['전년동기', '전년동기(%)']:
            if c in ci.columns:
                cols_to_drop.append(c)
        ci = ci.drop(cols_to_drop, axis=1)
        
        # 현금흐름표
        cf = tables2[4]
        cf.iloc[:, 0] = cf.iloc[:, 0].str.replace('계산에 참여한 계정 펼치기', '')
        cf.index = cf[accounting].values
        cf = cf.drop([accounting], axis=1)
        
        # 영업이익, 영업활동현금흐름 추출
        fs = pd.concat([ci, cf])
        # 인덱스 중복 방지를 위해 첫번째 매칭값만 가져옴
        fs = fs[~fs.index.duplicated(keep='first')]
        fs = fs.loc[['영업이익', '영업활동으로인한현금흐름'], :]
        fs = fs.rename(index={'영업활동으로인한현금흐름': '영업CF'})
        
        temp_df = pd.DataFrame({'CF이익비율': fs.loc['영업CF'].astype(float) / fs.loc['영업이익'].astype(float)}).T
        fs = pd.concat([fs, temp_df])
        
        temp1 = fs.loc['영업이익'].astype(float) > 0
        temp2 = fs.loc['영업CF'].astype(float) < 0
        temp_df = pd.DataFrame(temp1 & temp2, columns=['CF이익검토']).T
        fs = pd.concat([fs, temp_df])
        
        result['fs'] = fs
        
        return True, "", result
        
    except Exception as e:
        return False, str(e), {}
