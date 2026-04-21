from typing import List
import logging
from sqlalchemy.orm import Session

from src.database.repository import Repository
from src.database.models import TradeSignal, SignalType, SignalStatus, OrderType, HoldingStage, WatchStock
from src.srim.analyzer import analyze_stock
from src.strategy.signal import evaluate_signal, calculate_sell_quantity, calculate_buy_quantity
from src.config import get_config_value
from src.srim.models import SRIMResult

from src.kis_client.auth import KISAuth
from src.kis_client.account import KISAccount
from src.kis_client.market import KISMarket

logger = logging.getLogger(__name__)

class PortfolioManager:
    def __init__(self, db: Session, config: dict):
        self.repo = Repository(db)
        self.config = config
        self.required_ror = get_config_value(config, "trading", "required_ror_percent", default=8.0)
        self.buy_margin = get_config_value(config, "trading", "buy_margin", default=0.9)
        
        # KIS Clients
        self.auth = KISAuth(config)
        self.kis_account = KISAccount(self.auth, config)
        self.kis_market = KISMarket(self.auth)

    def _calculate_benchmark_amount(self) -> float:
        """Stage 0인 종목들의 평균 투자금액을 계산한다. 없을 경우 역산 또는 과거 기록 활용."""
        import os
        benchmark_file = "data/last_benchmark.txt"
        
        holdings = self.repo.db.query(HoldingStage).all()
        
        if not holdings:
            # 보유 종목이 아예 없으면 기본 설정 금액 사용
            base_amt = get_config_value(self.config, "trading", "base_investment_amount", default=1000000.0)
            return float(base_amt)
            
        # 1. Stage 0 평균 계산
        stage0_investments = [h.remaining_qty * h.avg_buy_price for h in holdings if h.stage == 0]
        if stage0_investments:
            avg_amount = sum(stage0_investments) / len(stage0_investments)
            os.makedirs("data", exist_ok=True)
            with open(benchmark_file, "w") as f: f.write(str(avg_amount))
            return avg_amount
            
        # 2. Stage 1에서 역산 (75% 비중 기준)
        stage1_investments = [h.remaining_qty * h.avg_buy_price for h in holdings if h.stage == 1]
        if stage1_investments:
            avg_amount = (sum(stage1_investments) / len(stage1_investments)) / 0.75
            os.makedirs("data", exist_ok=True)
            with open(benchmark_file, "w") as f: f.write(str(avg_amount))
            return avg_amount
            
        # 3. 마지막으로 사용했던 값 로드
        if os.path.exists(benchmark_file):
            try:
                with open(benchmark_file, "r") as f:
                    return float(f.read().strip())
            except Exception as e:
                logger.error(f"벤치마크 파일 읽기 실패: {e}")
                
        # 4. 최후의 보루: 설정된 기본 금액
        return float(get_config_value(self.config, "trading", "base_investment_amount", default=1000000.0))

    def sync_balance_with_broker(self) -> dict:
        """
        [하드 싱크] 한국투자증권 실제 계좌 잔고를 조회하여 로컬 DB의 HoldingStage를 강제 동기화한다.
        - 실제 계좌에 없는 종목(사용자가 HTS/MTS에서 수동 매도 등) → 로컬 DB에서도 삭제
        - 수량 또는 평단가가 다를 경우 → 증권사 데이터를 절대적 진실(Ground Truth)로 덮어씌움
        - 증권사 잔고에만 있는 종목(사용자가 수동 매수 등) → 로컬 DB에 Stage 0으로 신규 등록
        - Mock 모드이거나 API 호출 실패 시 → 아무것도 변경하지 않고 안전하게 스킵
        """
        broker_balance = self.kis_account.get_balance()

        # Mock 모드 또는 API 실패 시 None 반환 → 동기화 스킵
        if broker_balance is None:
            logger.info("잔고 동기화 스킵 (Mock 모드 또는 API 오류)")
            return {}

        local_holdings = self.repo.db.query(HoldingStage).all()
        local_codes = {h.code: h for h in local_holdings}

        # 1. 로컬 DB에만 있는 종목 처리 (실제로는 없는 종목 -> 삭제)
        for code, holding in local_codes.items():
            broker_data = broker_balance.get(code)
            if broker_data is None or broker_data.get("qty", 0) == 0:
                logger.warning(
                    f"[SYNC] {holding.name}({code}) 실제 계좌에 없음 → 로컬 DB에서 제거"
                )
                self.repo.remove_holding_stage(code)
            else:
                # 2. 양쪽 모두 있는 종목 처리 (불일치 시 덮어쓰기)
                broker_qty = broker_data["qty"]
                broker_avg = broker_data["avg_price"]
                
                qty_mismatch = holding.remaining_qty != broker_qty
                avg_mismatch = abs(holding.avg_buy_price - broker_avg) > 1  # 1원 이내 오차 허용

                if qty_mismatch or avg_mismatch:
                    logger.warning(
                        f"[SYNC] {holding.name}({code}) 불일치 감지 "
                        f"(DB: {holding.remaining_qty}주@{holding.avg_buy_price:.0f}원 "
                        f"→ 증권사: {broker_qty}주@{broker_avg:.0f}원) → 증권사 데이터로 덮어씌움"
                    )
                    # 비중 역산으로 Stage 재추론
                    benchmark_amount = self._calculate_benchmark_amount()
                    current_inv = broker_qty * broker_avg
                    ratio = current_inv / benchmark_amount if benchmark_amount > 0 else 1.0
                    if ratio > 0.875: inferred_stage = 0
                    elif ratio > 0.625: inferred_stage = 1
                    elif ratio > 0.375: inferred_stage = 2
                    else: inferred_stage = 3

                    self.repo.upsert_holding_stage(
                        code, holding.name, stage=inferred_stage,
                        total_buy_qty=holding.total_buy_qty,
                        remaining_qty=broker_qty,
                        avg_buy_price=broker_avg
                    )

        # 3. 증권사 잔고에만 있는 종목 처리 (수동 매수 등 -> 신규 등록)
        for broker_code, broker_data in broker_balance.items():
            if broker_code not in local_codes and broker_data.get("qty", 0) > 0:
                broker_qty = broker_data["qty"]
                broker_avg = broker_data["avg_price"]
                logger.warning(
                    f"[SYNC] 미등록 종목({broker_code}) 발견 "
                    f"({broker_qty}주@{broker_avg:.0f}원) → 로컬 DB에 Stage 0으로 신규 편입"
                )
                self.repo.upsert_holding_stage(
                    broker_code, "미등록(HTS매수)", stage=0,
                    total_buy_qty=broker_qty,
                    remaining_qty=broker_qty,
                    avg_buy_price=broker_avg
                )

        logger.info(f"잔고 동기화 완료 (증권사 보유 {len(broker_balance)}종목 확인)")
        return broker_balance

    def analyze_holdings(self):
        """새벽 3시: 보유 중인 종목들만 집중 분석하여 S-RIM 목표가 갱신"""
        # Step 0: 분석 시작 전 증권사 실제 잔고와 로컬 DB를 강제 동기화
        self.sync_balance_with_broker()

        holdings = self.repo.db.query(HoldingStage).all()
        logger.info(f"보유 종목 {len(holdings)}개 분석 시작...")
        
        for h in holdings:
            srim_result = analyze_stock(h.code, h.name, "", "", self.required_ror)
            if srim_result:
                self.repo.add_watch_stock(
                    h.code, h.name, srim_result.industry, srim_result.product,
                    srim_result.buy_target_price, srim_result.sell_target_1,
                    srim_result.sell_target_2, srim_result.sell_target_3, srim_result.sell_target_4,
                    roe=srim_result.roe, buy_yield=srim_result.buy_yield
                )
        logger.info("보유 종목 분석 완료.")


    def analyze_full_market(self):
        """새벽 4시: KRX 전체 종목을 분석하여 매수 후보군 발굴"""
        from src.srim.data_fetcher import get_krx_list
        krx_df = get_krx_list()
        logger.info(f"KRX 전체 {len(krx_df)}개 종목 분석 시작 (새벽 4시 배치)...")
        
        for _, row in krx_df.iterrows():
            # 11가지 필터링 조건을 통과하는지 확인
            # (analyze_stock 내부에 is_buy_candidate 로직 포함)
            srim_result = analyze_stock(row['code'], row['name'], row['industry'], row['product'], self.required_ror)
            
            if srim_result and srim_result.is_buy_candidate(self.required_ror, self.buy_margin):
                logger.info(f"✨ 매수 후보 발견: {row['name']} ({row['code']})")
                self.repo.add_watch_stock(
                    row['code'], row['name'], srim_result.industry, srim_result.product,
                    srim_result.buy_target_price, srim_result.sell_target_1,
                    srim_result.sell_target_2, srim_result.sell_target_3, srim_result.sell_target_4,
                    roe=srim_result.roe, buy_yield=srim_result.buy_yield
                )
        logger.info("KRX 전체 분석 완료.")

    def monitor_signals(self, available_cash: int):
        """장중: 보유 종목 및 매수 후보 종목들의 실시간 가격만 체크하여 시그널 발생"""
        holdings = self.repo.db.query(HoldingStage).all()
        candidates = self.repo.get_watch_stocks(active_only=True)
        
        codes = {h.code for h in holdings} | {c.code for c in candidates}
        benchmark_amount = self._calculate_benchmark_amount()
        
        potential_signals = []
        
        for code in codes:
            stock = self.repo.db.query(WatchStock).filter(WatchStock.code == code).first()
            if not stock: continue
            
            # KIS API 연동 실시간 가격
            current_price = self.kis_market.get_current_price(stock.code)
            if not current_price:
                current_price = stock.buy_target_price # API 오류 시 백업
            
            srim = SRIMResult(
                code=stock.code, name=stock.name, industry=stock.industry, product=stock.product,
                current_price=current_price, 
                buy_target_price=stock.buy_target_price,
                sell_target_1=stock.sell_target_1, sell_target_2=stock.sell_target_2,
                sell_target_3=stock.sell_target_3, sell_target_4=stock.sell_target_4,
                buy_yield=stock.buy_yield, target_1_yield=0, target_2_yield=0, target_3_yield=0, target_4_yield=0,
                roe=stock.roe, roe_reference="", dividend_yield=0, dividend_payout_ratio=0,
                cf_risk_count=0, cf_to_op_avg=0, net_income_4q_sum=0, net_income_deficit_count=0,
                op_income_4q_sum=0, op_income_deficit_count=0
            )
            
            holding = self.repo.get_holding_stage(code)
            sig_type, target_p = evaluate_signal(srim, holding, self.required_ror, benchmark_amount, self.buy_margin)
            
            if sig_type:
                # Mix Score 5:5 계산
                yield_score = min(stock.buy_yield, 100) / 100.0
                quality_score = min(stock.roe / self.required_ror, 4.0) / 4.0 if self.required_ror > 0 else 0
                composite_score = (yield_score * 0.5) + (quality_score * 0.5)
                
                potential_signals.append({
                    'stock': stock, 'srim': srim, 'holding': holding,
                    'type': sig_type, 'target_price': target_p,
                    'score': composite_score,
                    'is_addon': holding is not None and sig_type == SignalType.BUY
                })

        sell_signals = [sig for sig in potential_signals if sig['type'] != SignalType.BUY]
        buy_signals = [sig for sig in potential_signals if sig['type'] == SignalType.BUY]

        # 1. 매도 시그널 0순위 전량 집행 (가용 현금 확보 목적)
        for sig in sell_signals:
            holding = self.repo.get_holding_stage(sig['stock'].code)
            if holding:
                sell_qty = calculate_sell_quantity(holding, sig['type'], benchmark_amount)
                if sell_qty <= 0: continue

                logger.info(f"[{sig['stock'].code}] {sig['type'].name} 집행 (수량: {sell_qty}주 @ {sig['srim'].current_price:,}원)")
                new_sig = self.repo.add_signal(sig['stock'].code, sig['stock'].name, sig['type'], sig['srim'].current_price, sig['target_price'])
                
                # 원자적 처리: 주문 발송 + 로컬 DB(HoldingStage) 업데이트
                success = self.execute_signal(new_sig.id, sig['srim'].current_price, sell_qty)
                if success:
                    logger.info(f"[{sig['stock'].code}] SELL 체결 및 DB 갱신 완료")
                else:
                    logger.error(f"[{sig['stock'].code}] SELL 주문 실패")

        # 2. 매도 완료 후 최신 가용 현금 확보
        remaining_cash = self.kis_account.get_available_cash()
        
        # 3. 매수 시그널 정렬 (1순위 추가매수, 2순위 종합점수 높은 순)
        buy_signals.sort(key=lambda x: (x['is_addon'], x['score']), reverse=True)

        for sig in buy_signals:
            qty = calculate_buy_quantity(sig['holding'], sig['srim'], benchmark_amount)
            if qty <= 0: continue

            needed_cash = int(qty * sig['srim'].current_price * 1.01)

            if remaining_cash >= needed_cash:
                logger.info(f"[{sig['stock'].code}] BUY 집행 (점수: {sig['score']:.2f}, 수량: {qty}, 필요현금: {needed_cash:,}원)")
                new_sig = self.repo.add_signal(sig['stock'].code, sig['stock'].name, sig['type'], sig['srim'].current_price, sig['target_price'])
                
                # 원자적 처리: 주문 발송 + 로컬 DB 업데이트 (무한 매수 방지)
                success = self.execute_signal(new_sig.id, sig['srim'].current_price, qty)
                if success:
                    remaining_cash = self.kis_account.get_available_cash()
                    logger.info(f"[{sig['stock'].code}] BUY 체결 완료 → 갱신된 잔여 현금: {remaining_cash:,}원")
                else:
                    logger.error(f"[{sig['stock'].code}] BUY 주문 실패")
            else:
                logger.info(f"[{sig['stock'].code}] 현금 부족으로 BUY 스킵 (필요: {needed_cash:,}원, 잔고: {remaining_cash:,}원)")


    def execute_signal(self, signal_id: int, execution_price: int, execution_qty: int):
        """
        발생한 시그널을 실행(매수/매도 완료) 처리한다.
        실제 KIS API 주문이 완료된 후 이 함수가 호출되어야 한다.
        """
        signal = self.repo.db.query(TradeSignal).filter(TradeSignal.id == signal_id).first()
        if not signal or signal.status != SignalStatus.PENDING:
            return False
            
        order_type_str = "BUY" if signal.signal_type == SignalType.BUY else "SELL"
        
        # 1. KIS API 실제 주문 발송
        success = self.kis_account.place_order(signal.code, execution_qty, execution_price, order_type_str)
        if not success:
            logger.error(f"주문 실패로 인해 시그널({signal_id}) 집행 취소")
            return False
        
        order_type = OrderType.BUY if signal.signal_type == SignalType.BUY else OrderType.SELL
        
        # 주문 히스토리 추가
        self.repo.add_order(
            signal.code, signal.name, order_type, execution_qty, execution_price, signal_id
        )
        
        # 보유 상태 업데이트
        holding = self.repo.get_holding_stage(signal.code)
        
        if signal.signal_type == SignalType.BUY:
            if not holding:
                self.repo.upsert_holding_stage(
                    signal.code, signal.name, stage=0, 
                    total_buy_qty=execution_qty, remaining_qty=execution_qty, avg_buy_price=execution_price
                )
            else:
                # 추가 매수
                new_total = holding.total_buy_qty + execution_qty
                new_remain = holding.remaining_qty + execution_qty
                new_avg = ((holding.avg_buy_price * holding.remaining_qty) + (execution_price * execution_qty)) / new_remain
                self.repo.upsert_holding_stage(
                    signal.code, signal.name, stage=holding.stage,
                    total_buy_qty=new_total, remaining_qty=new_remain, avg_buy_price=new_avg
                )
                
        else: # SELL
            if holding:
                new_remain = max(0, holding.remaining_qty - execution_qty)
                
                # 스테이지 업데이트
                new_stage = holding.stage
                if signal.signal_type == SignalType.SELL_STAGE_1:
                    new_stage = 1
                elif signal.signal_type == SignalType.SELL_STAGE_2:
                    new_stage = 2
                elif signal.signal_type == SignalType.SELL_STAGE_3:
                    new_stage = 3
                elif signal.signal_type in (SignalType.SELL_STAGE_4, SignalType.FORCE_SELL):
                    new_stage = 4
                    
                if new_remain == 0:
                    self.repo.remove_holding_stage(signal.code)
                else:
                    self.repo.upsert_holding_stage(
                        signal.code, signal.name, stage=new_stage,
                        total_buy_qty=holding.total_buy_qty, remaining_qty=new_remain, avg_buy_price=holding.avg_buy_price
                    )
        
        self.repo.update_signal_status(signal_id, SignalStatus.EXECUTED)
        return True
