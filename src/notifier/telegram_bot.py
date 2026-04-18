import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes

from src.config import get_config_value
from src.database import SessionLocal
from src.database.repository import Repository
from src.database.models import SignalStatus
from src.strategy.portfolio_manager import PortfolioManager

logger = logging.getLogger(__name__)

class TelegramNotifier:
    def __init__(self, config: dict):
        self.config = config
        self.token = get_config_value(config, "telegram", "bot_token")
        self.chat_id = get_config_value(config, "telegram", "chat_id")
        self.app = Application.builder().token(self.token).build() if self.token else None
        
        if self.app:
            self.app.add_handler(CommandHandler("start", self.cmd_start))
            self.app.add_handler(CallbackQueryHandler(self.handle_approval))

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        await update.message.reply_text("Autonomous S-RIM Bot Started.\nI will notify you of any trade signals.")

    async def handle_approval(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        query = update.callback_query
        await query.answer()
        
        # data format: action_signalId (e.g. "approve_12", "reject_12")
        data = query.data.split("_")
        if len(data) != 2:
            return
            
        action, sig_id_str = data
        sig_id = int(sig_id_str)
        
        db = SessionLocal()
        try:
            repo = Repository(db)
            pm = PortfolioManager(db, self.config)
            
            if action == "approve":
                # KIS API 연동 후 실제 실행하는 로직이 여기에 들어가야 함
                # 현재는 시뮬레이션
                pm.execute_signal(sig_id, execution_price=0, execution_qty=0) # 가격/수량은 KIS 연동시 실제 체결가 적용
                await query.edit_message_text(text=f"✅ Signal {sig_id} Approved & Executed.")
            elif action == "reject":
                repo.update_signal_status(sig_id, SignalStatus.REJECTED)
                await query.edit_message_text(text=f"❌ Signal {sig_id} Rejected.")
        except Exception as e:
            logger.error(f"Approval handling error: {e}")
            await query.edit_message_text(text=f"Error executing signal: {str(e)}")
        finally:
            db.close()

    async def send_signal_notification(self, signal_id: int, code: str, name: str, sig_type: str, price: int, require_approval: bool):
        if not self.app or not self.chat_id:
            logger.warning("Telegram bot not configured.")
            return

        msg = f"🔔 **TRADE SIGNAL** 🔔\n\n"
        msg += f"[{code}] {name}\n"
        msg += f"Type: {sig_type}\n"
        msg += f"Current Price: ₩{price:,}\n"
        
        if require_approval:
            msg += "\nDo you approve this trade?"
            keyboard = [
                [
                    InlineKeyboardButton("Approve ✅", callback_data=f"approve_{signal_id}"),
                    InlineKeyboardButton("Reject ❌", callback_data=f"reject_{signal_id}"),
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await self.app.bot.send_message(chat_id=self.chat_id, text=msg, reply_markup=reply_markup)
        else:
            msg += "\n✅ Executed Automatically."
            await self.app.bot.send_message(chat_id=self.chat_id, text=msg)
            
    async def send_message(self, text: str):
        if self.app and self.chat_id:
            await self.app.bot.send_message(chat_id=self.chat_id, text=text)

    def start_polling(self):
        """별도 스레드나 비동기 태스크에서 실행해야 함"""
        if self.app:
            self.app.run_polling()
