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
        
        interval = get_config_value(config, "trading", "monitoring_interval_min", default=10)
        
        # 장중 모니터링: 월-금 09:00 ~ 15:30
        self.scheduler.add_job(
            self.market_monitoring_job,
            CronTrigger(day_of_week='mon-fri', hour='9-15', minute=f'*/{interval}'),
            id="market_monitoring",
            name="장중 가격 모니터링 및 시그널 체크",
            replace_existing=True
        )

    async def market_monitoring_job(self):
        """장중 모니터링을 수행하고 시그널이 생기면 텔레그램으로 알림을 보냅니다."""
        logger.info("Market monitoring job started.")
        db = SessionLocal()
        try:
            pm = PortfolioManager(db, self.config)
            pm.scan_watch_stocks()
            
            # 새롭게 생성된(Pending) 시그널 전송 로직
            # 실제로는 DB 쿼리를 통해 최근 1분(또는 interval) 내 생성된 시그널을 찾아야 함
            # 여기서는 예시로 pending_signals를 모두 가져옴
            signals = pm.repo.get_pending_signals()
            auto_trade = get_config_value(self.config, "trading", "auto_trade", default=False)
            
            for sig in signals:
                if self.notifier:
                    await self.notifier.send_signal_notification(
                        signal_id=sig.id,
                        code=sig.code,
                        name=sig.name,
                        sig_type=sig.signal_type.name,
                        price=sig.current_price,
                        require_approval=not auto_trade
                    )
                
                # 자동 매매 모드인 경우 승인 대기 없이 즉시 체결로 넘김 (시뮬레이션)
                if auto_trade:
                    pm.execute_signal(sig.id, execution_price=sig.current_price, execution_qty=0) # Qty는 추후 KIS 적용시 계산
                    
        except Exception as e:
            logger.error(f"Error in monitoring job: {e}")
        finally:
            db.close()
            logger.info("Market monitoring job finished.")

    def start(self):
        self.scheduler.start()
        logger.info("Scheduler started.")

    def stop(self):
        self.scheduler.shutdown()
        logger.info("Scheduler stopped.")
