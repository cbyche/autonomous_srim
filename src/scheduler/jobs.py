import logging
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from src.database import SessionLocal
from src.strategy.portfolio_manager import PortfolioManager
from src.config import get_config_value

logger = logging.getLogger(__name__)

class SchedulerManager:
    def __init__(self, config: dict, notifier=None):
        self.config = config
        self.notifier = notifier
        self.scheduler = AsyncIOScheduler()
        self._setup_jobs()

    def update_config_and_reload(self, new_config: dict):
        """설정을 업데이트하고 스케줄을 재등록한다."""
        self.config = new_config
        self._setup_jobs()
        logger.info("Scheduler jobs reloaded with new configuration.")

    def _setup_jobs(self):
        """설정에 따라 분석 스케줄을 등록한다."""
        # 1. 보유 종목 분석 (03:00 AM)
        holdings_mode = get_config_value(self.config, "scheduler", "holdings_analysis_mode", default="daily")
        h_trigger = CronTrigger(day_of_week='mon-fri', hour=3, minute=0) if holdings_mode == "daily" else CronTrigger(day_of_week='sat', hour=3, minute=0)
        
        self.scheduler.add_job(
            self.holdings_analysis_job,
            h_trigger,
            id="holdings_analysis",
            name="보유 종목 S-RIM 분석 (03:00)",
            replace_existing=True
        )

        # 2. KRX 전체 분석 (04:00 AM)
        market_mode = get_config_value(self.config, "scheduler", "market_analysis_mode", default="weekly")
        m_trigger = CronTrigger(day_of_week='mon-fri', hour=4, minute=0) if market_mode == "daily" else CronTrigger(day_of_week='sat', hour=4, minute=0)
        
        self.scheduler.add_job(
            self.market_analysis_job,
            m_trigger,
            id="market_analysis",
            name="KRX 전체 S-RIM 분석 (04:00)",
            replace_existing=True
        )

        # 3. 장중 모니터링 (현재가 기반 시그널 체크)
        interval = get_config_value(self.config, "trading", "monitoring_interval_min", default=10)
        self.scheduler.add_job(
            self.intraday_monitoring_job,
            CronTrigger(day_of_week='mon-fri', hour='9-15', minute=f'*/{interval}'),
            id="intraday_monitoring",
            name="장중 시그널 모니터링",
            replace_existing=True
        )

    async def holdings_analysis_job(self):
        """새벽 3시: 보유 종목의 재무 데이터를 갱신하고 S-RIM 가격 재산출"""
        logger.info("Starting scheduled holdings analysis (03:00)...")
        db = SessionLocal()
        try:
            pm = PortfolioManager(db, self.config)
            pm.analyze_holdings()
        finally:
            db.close()

    async def market_analysis_job(self):
        """새벽 4시: KRX 전 종목 분석 및 매수 후보 발굴"""
        logger.info("Starting scheduled full market analysis (04:00)...")
        db = SessionLocal()
        try:
            pm = PortfolioManager(db, self.config)
            pm.analyze_full_market()
        finally:
            db.close()

    async def intraday_monitoring_job(self):
        """장중: 현재가 기반으로 기 산출된 S-RIM 가격과 대조하여 시그널 발생"""
        db = SessionLocal()
        try:
            pm = PortfolioManager(db, self.config)

            # 매 사이클마다 KIS API에서 실제 주문 가능 현금을 새로 조회
            # (이전 사이클 매수 체결로 줄어든 현금이 즉시 반영됨)
            available_cash = pm.kis_account.get_available_cash()
            logger.info(f"장중 모니터링 시작 — 주문 가능 현금: {available_cash:,}원")

            pm.monitor_signals(available_cash=available_cash)

            # 발생한 시그널 텔레그램 알림
            signals = pm.repo.get_pending_signals()
            for sig in signals:
                if self.notifier:
                    await self.notifier.send_signal_notification(
                        signal_id=sig.id, code=sig.code, name=sig.name,
                        sig_type=sig.signal_type.name, price=sig.current_price
                    )
        finally:
            db.close()

    def start(self):
        self.scheduler.start()
        logger.info("Scheduler started.")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("Scheduler stopped.")
