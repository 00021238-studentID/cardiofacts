import logging
from telegram import constants, Update, Bot
from telegram.ext import filters, CommandHandler, MessageHandler, ContextTypes, ApplicationBuilder, Application
from telegram.helpers import escape_markdown
import os
from dotenv import load_dotenv
import asyncio
import datetime
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import pytz

load_dotenv()

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

TOKEN = os.getenv('TOKEN') or ''
OWNER_ID = int(os.getenv('OWNER') or '0')
CHANNNEL_ID = int(os.getenv('CHANNEL_ID') or '0')

is_allowed = False
is_today_sent = False

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id == OWNER_ID:
        global is_allowed
        is_allowed = True
        await context.bot.send_message(
            chat_id=user.id,
            text=f'Assalamu alaykum 🤝\n\nXush kelibsiz, *Abdulloh* aka.',
            reply_to_message_id=update.effective_message.message_id,
            parse_mode=constants.ParseMode.MARKDOWN
        )
        await update.message.reply_text('Kanalga post qilish boshlandi!')
    return

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id == OWNER_ID:
        global is_allowed
        is_allowed = False
        await context.bot.send_message(
            chat_id=user.id,
            text=f'Kanalga post qilish tugatildi, *Abdulloh* aka.',
            reply_to_message_id=update.effective_message.message_id,
            parse_mode=constants.ParseMode.MARKDOWN
        )
    return

async def set_file(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user

    if user.id == OWNER_ID:
        try:
            document = update.message.document
            received_file = await context.bot.get_file(document.file_id)
            await received_file.download_to_drive('facts.txt')
        except Exception as e:
            await update.message.reply_text("Yuborilgan file'ni saqlashda xatolik:", str(e))
            logger.error('Error while saving uploaded doc:', str(e))

        await update.message.reply_text("Yuborilgan file muvvaffaqiyatli saqlandi ✅")
        logger.info('Uploaded document is saved successfully.')
    return

async def _send_one_fact(bot: Bot, chat_id: int) -> None:
    """
    Reads the first fact, sends it, and removes it from facts.txt.
    """
    global is_today_sent
    fact_sent = False

    try:
        fact = ''
        with open('facts.txt', 'r+', encoding='utf-8') as file:
            lines = file.readlines()
            if not lines:
                await bot.send_message(chat_id=chat_id, text='File facts.txt bo\'sh ekan.')
                logger.info('File facts.txt is empty. No fact to send.')
                return

            fact = lines[0].strip()

            await bot.send_photo(
                chat_id=chat_id,
                photo='picture.png',
                caption=f'\\#daily\\_fact\n\n💬 *{escape_markdown(fact, version=2)}*\n\n\\@CardioScope — yuragingizga quloq tuting.',
                parse_mode=constants.ParseMode.MARKDOWN_V2
            )
            await bot.send_message(chat_id=OWNER_ID, text="Fakt jo'natildi ✅")
            logger.info(f"Fact '{fact}' sent successfully to chat_id {chat_id}.")

            if len(lines) > 1:
                new_lines = lines[1:]
                file.seek(0)
                file.truncate(0)
                file.writelines(new_lines)
                await bot.send_message(chat_id=OWNER_ID, text=f'{len(new_lines)} - shuncha faktlar qoldi.')
            else:
                file.seek(0)
                file.truncate(0)
                await bot.send_message(chat_id=OWNER_ID, text='facts.txt bo\'shadi 🤷‍♂️')
                logger.info('facts.txt is finished.')

            fact_sent = True
    except FileNotFoundError:
        await bot.send_message(chat_id=chat_id, text="Error: 'facts.txt' topilmadi.")
        logger.error("Error: 'facts.txt' not found.")
    except Exception as e:
        await bot.send_message(chat_id=chat_id, text=f"Jo'natishda xatolik yuzaga keldi: {e}")
        logger.error(f'Error during fact sending: {e}')

    if fact_sent:
        is_today_sent = True

async def send(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    if user.id == OWNER_ID:
        if not is_allowed:
            await update.message.reply_text("Fakt jo'natishni boshlashga ruxsat berilmagan. \n\n/start - boshlash uchun.")
            return

        await _send_one_fact(context.bot, CHANNNEL_ID)
        if is_today_sent:
             await update.message.reply_text("Fakt jo'natildi ✅")
        else:
             await update.message.reply_text("Fakt jo'natilmadi (tekshiring loglarni/xatolarni).")

async def daily_scheduled_send(bot: Bot) -> None:
    global is_allowed, is_today_sent
    logger.info(f"Daily scheduled task triggered. is_allowed: {is_allowed}, is_today_sent: {is_today_sent}")

    if is_allowed and not is_today_sent:
        await _send_one_fact(bot, CHANNNEL_ID)
    elif not is_allowed:
        logger.info("Daily send skipped: is_allowed is False.")
        await bot.send_message(chat_id=OWNER_ID, text="Kunlik fakt jo'natish *post qo'yish* o'chirilganligi sababli o'tkazib yuborildi.", parse_mode=constants.ParseMode.MARKDOWN_V2)
    elif is_today_sent:
        logger.info("Daily send skipped: Fact already sent today.")
        await bot.send_message(chat_id=OWNER_ID, text="Kunlik fakt bugun allaqachon jo'natilgan.")

async def daily_reset_flag(bot: Bot) -> None:
    global is_today_sent
    if is_today_sent:
        is_today_sent = False
        logger.info("is_today_sent flag reset for the new day.")
        await bot.send_message(chat_id=OWNER_ID, text="Kunlik avto fakt jo'natish ruxsati tiklandi.")
    else:
        logger.info("is_today_sent was already False, no reset needed.")

async def post_init_setup(application: Application):
    """Initializes and starts the scheduler after the bot has started."""
    scheduler = AsyncIOScheduler()
    tashkent_tz = pytz.timezone('Asia/Tashkent')

    scheduler.add_job(
        daily_scheduled_send,
        CronTrigger(hour=8, minute=00, timezone=tashkent_tz),
        name='Daily Fact Sender',
        id='daily_fact_sender',
        args=[application.bot]
    )
    logger.info(f"Scheduled 'Daily Fact Sender' to run daily at 01:15 UTC+5.")

    scheduler.add_job(
        daily_reset_flag,
        CronTrigger(hour=0, minute=0, timezone=tashkent_tz),
        name='Daily Reset Flag',
        id='daily_reset_flag',
        args=[application.bot]
    )
    logger.info(f"Scheduled 'Daily Reset Flag' to run daily at 00:00 UTC+5.")

    scheduler.start()
    logger.info('APScheduler started after bot initialization.')

def main() -> None:
    application = ApplicationBuilder().token(TOKEN).build()
    
    # Assign the setup function to the post_init property
    application.post_init = post_init_setup

    application.add_handler(CommandHandler('start', start))
    application.add_handler(CommandHandler('cancel', cancel))
    application.add_handler(CommandHandler('send', send))
    application.add_handler(MessageHandler(filters.Document.TXT, set_file))

    logger.info('Bot is polling...')
    application.run_polling(drop_pending_updates=True)


if __name__=='__main__':
    main()