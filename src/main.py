import asyncio
import logging
import argparse
import uvicorn
import threading

from src.config import load_config
from src.database import init_db
from src.notifier.telegram_bot import TelegramNotifier
from src.scheduler.jobs import SchedulerManager

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_web_server(app_instance):
    """FastAPI 웹 대시보드를 실행합니다."""
    logger.info("Starting Web Dashboard on port 8000...")
    uvicorn.run(app_instance, host="0.0.0.0", port=8000, log_level="info")

async def main():
    parser = argparse.ArgumentParser(description="Autonomous S-RIM Trading System")
    parser.add_argument("--web", action="store_true", help="Start the web dashboard")
    parser.add_argument("--bot", action="store_true", help="Start the telegram bot")
    parser.add_argument("--schedule", action="store_true", help="Start the market monitoring scheduler")
    parser.add_argument("--all", action="store_true", help="Start all components (web, bot, schedule)")
    args = parser.parse_args()

    # 설정 로드
    config = load_config()
    
    # DB 초기화
    logger.info("Initializing Database...")
    init_db()

    # 인자가 없으면 도움말 표시
    if not any([args.web, args.bot, args.schedule, args.all]):
        parser.print_help()
        return

    from src.web.app import app
    notifier = None
    
    # 2. 텔레그램 봇 초기화
    if args.bot or args.all:
        logger.info("Initializing Telegram Notifier...")
        notifier = TelegramNotifier(config)

    # 3. 스케줄러 시작
    if args.schedule or args.all:
        logger.info("Initializing Scheduler...")
        scheduler = SchedulerManager(config, notifier=notifier)
        scheduler.start()
        app.state.scheduler = scheduler

    # 1. 웹 서버 시작 (백그라운드 스레드)
    if args.web or args.all:
        web_thread = threading.Thread(target=run_web_server, args=(app,), daemon=True)
        web_thread.start()

    # 4. 텔레그램 봇 실행 (메인 스레드 점유)
    if notifier and (args.bot or args.all):
        logger.info("Starting Telegram Bot Polling...")
        # run_polling은 블로킹 함수이므로 가장 마지막에 실행합니다.
        notifier.app.run_polling()
    else:
        # 봇을 실행하지 않으면 스크립트가 종료되지 않도록 무한 루프 유지
        try:
            while True:
                await asyncio.sleep(3600)
        except (KeyboardInterrupt, SystemExit):
            pass

if __name__ == "__main__":
    asyncio.run(main())
