import logging
import sys
import os
import json
import urllib.request

# Ręczne ładowanie .env (zamiast python-dotenv)
_env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
if os.path.exists(_env_path):
    with open(_env_path) as _f:
        for _line in _f:
            _line = _line.strip()
            if _line and not _line.startswith('#') and '=' in _line:
                _k, _v = _line.split('=', 1)
                os.environ.setdefault(_k.strip(), _v.strip())

sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))
from src.api.users_db import process_paid_invoice

try:
    from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, WebAppInfo
    from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes
except ImportError:
    print("Please pip install python-telegram-bot requests python-dotenv")
    sys.exit(1)

logging.basicConfig(level=logging.INFO)

# Token from BotFather
TOKEN = "8693332191:AAGkwkmKBUTan_d8hKc8e0bwDGrMOAV59HA"
CRYPTO_PAY_TOKEN = os.getenv("CRYPTOPAY_TOKEN")

# The web app URL. Since Telegram requires HTTPS, for local testing without ngrok
# users won't be able to open the app inside Telegram unless they use Ngrok.
# However, you can put a generic valid https url or a dummy localtunnel url here.
WEB_APP_URL = "https://landing-sight-bridal-revised.trycloudflare.com"

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Send a message with a button that opens the web app."""
    chat_id = update.effective_chat.id
    
    # Przechwytywanie polecenia (referral)
    referred_by = None
    if context.args:
        try:
            potential_ref = int(context.args[0])
            if potential_ref != chat_id: # Nie można polecić samego siebie
                referred_by = potential_ref
        except ValueError:
            pass
    
    # Rejestracja użytkownika w bazie (z polecającym jeśli istnieje)
    from src.api.users_db import upsert_user
    upsert_user(chat_id, referred_by)
    
    # We create a button that launches the Web App pointing to our URL
    keyboard = [
        [InlineKeyboardButton("⚡ Otwórz Market Terminal", web_app=WebAppInfo(url=WEB_APP_URL))]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "Większość traderów reaguje na cenę. Ty widzisz przepływy zanim wykres się ruszy.\n\n"
        "💡 **PRO TIP:** Zaproś 3 znajomych do bota, aby odblokować terminal PRO na stałe za darmo.\n\n"
        "Kliknij poniżej, by poznać prawdę rynkową."
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup, parse_mode="Markdown")

def create_crypto_invoice(telegram_id: int):
    url = "https://pay.crypt.bot/api/createInvoice"
    payload = json.dumps({
        "asset": "USDT",
        "amount": "49.00",
        "description": "Vortex PRO (Lifetime Access)",
        "payload": f"upgrade_{telegram_id}"
    }).encode('utf-8')
    req = urllib.request.Request(url, data=payload, method='POST')
    req.add_header('Crypto-Pay-API-Token', CRYPTO_PAY_TOKEN)
    req.add_header('Content-Type', 'application/json')
    req.add_header('User-Agent', 'Mozilla/5.0')
    with urllib.request.urlopen(req, timeout=10) as response:
        resp = json.loads(response.read().decode())
    if resp.get("ok"):
        return resp["result"]["pay_url"], resp["result"]["invoice_id"]
    raise Exception(f"Invoice error: {resp}")

async def upgrade(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not CRYPTO_PAY_TOKEN:
        await update.message.reply_text("Bramka płatnicza w trybie konserwacji.")
        return
    
    chat_id = update.effective_chat.id
    try:
        pay_url, inv_id = create_crypto_invoice(chat_id)
        keyboard = [[InlineKeyboardButton("💳 ZAPŁAĆ 49 USDT (Krypto)", url=pay_url)]]
        text = "⚡ ODBLOKUJ PEŁEN POTENCJAŁ\n\nNielimitowany podgląd portfeli wielorybów na wyciągnięcie ręki. Używamy natywnego Telegram Crypto Pay (bez prowizji banków)."
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    except Exception as e:
        await update.message.reply_text(f"Błąd uruchamiania faktury: {e}")

async def poll_invoices(context: ContextTypes.DEFAULT_TYPE):
    """Sprawdza co 15 sekund czy ktoś opłacił wyzwolone faktury z Crypto Pay."""
    if not CRYPTO_PAY_TOKEN: return
    
    url = "https://pay.crypt.bot/api/getInvoices?status=paid" + "&" + "count=20"
    req = urllib.request.Request(url)
    req.add_header('Crypto-Pay-API-Token', CRYPTO_PAY_TOKEN)
    req.add_header('User-Agent', 'Mozilla/5.0')
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            resp = json.loads(response.read().decode())
        if resp.get("ok"):
            for inv in resp["result"]["items"]:
                inv_id = inv["invoice_id"]
                payload = inv.get("payload", "")
                if payload.startswith("upgrade_"):
                    telegram_id = int(payload.split("_")[1])
                    
                    # Spróbuj zapisać = True jeśli to nowa wpłata nieistniejąca w bazie
                    if process_paid_invoice(inv_id, telegram_id):
                        msg = "✅ **ZAKSIĘGOWANO PŁATNOŚĆ!**\n\nWitaj po drugiej stronie. Możesz rozpocząć polowanie otwierając /start"
                        await context.bot.send_message(chat_id=telegram_id, text=msg, parse_mode="Markdown")
                        print(f"User {telegram_id} upgraded to PRO limit via cryptopay!")
    except Exception as e:
        print(f"Invoice polling error: {e}")

def main():
    app = ApplicationBuilder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("upgrade", upgrade))
    
    # Dodajemy zadanie w tle (odpytywanie co 15 sekund by wyłapać Twoich klientów natychmiast)
    job_queue = app.job_queue
    job_queue.run_repeating(poll_invoices, interval=15, first=5)
    
    print("🤖 Bot is starting up with CryptoPay Enabled... Press Ctrl+C to stop.")
    app.run_polling()

if __name__ == "__main__":
    main()
