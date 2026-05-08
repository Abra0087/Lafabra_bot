import os
import asyncio
import logging
import httpx
from bs4 import BeautifulSoup
from telegram import Bot, Update
from telegram.ext import Application, CommandHandler, ContextTypes

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

TOKEN = os.environ.get("BOT_TOKEN", "INSERISCI_QUI_IL_TUO_TOKEN")
CHANNEL_ID = os.environ.get("CHANNEL_ID", "")  # Es: @topofferte02
AFFILIATE_TAG = "topofferte02-21"

WATCHLIST = [
    {"asin": "B0BLGJHQLJ", "name": "Profumo Khamrah Lattafa", "max_price": 35.0},
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept-Language": "it-IT,it;q=0.9",
}

async def get_amazon_price(asin: str) -> dict:
    url = f"https://www.amazon.it/dp/{asin}"
    try:
        async with httpx.AsyncClient(headers=HEADERS, follow_redirects=True, timeout=15) as client:
            response = await client.get(url)
            soup = BeautifulSoup(response.text, "html.parser")
            price_el = soup.select_one(".a-price .a-offscreen")
            if price_el:
                price_text = price_el.text.strip().replace("€", "").replace(",", ".").strip()
                price = float(price_text)
            else:
                price = None
            title_el = soup.select_one("#productTitle")
            title = title_el.text.strip()[:60] if title_el else "Prodotto"
            original_el = soup.select_one(".a-price.a-text-price .a-offscreen")
            original = None
            if original_el:
                orig_text = original_el.text.strip().replace("€", "").replace(",", ".").strip()
                try:
                    original = float(orig_text)
                except:
                    pass
            return {"price": price, "original": original, "title": title, "asin": asin}
    except Exception as e:
        logger.error(f"Errore per ASIN {asin}: {e}")
        return {"price": None, "original": None, "title": "N/A", "asin": asin}

def build_affiliate_link(asin: str) -> str:
    return f"https://www.amazon.it/dp/{asin}?tag={AFFILIATE_TAG}"

def format_offer_message(product: dict, current_price: float, original_price: float) -> str:
    discount = 0
    if original_price and original_price > 0:
        discount = int(((original_price - current_price) / original_price) * 100)
    link = build_affiliate_link(product["asin"])
    msg = f"""🔥 NUOVA OFFERTA RILEVATA!

⌚ {product['name']}

❌ Prezzo originale: {f"{original_price:.2f}€" if original_price else 'N/A'}
✅ Prezzo attuale: {current_price:.2f}€
📉 Sconto: -{discount}%

👉 {link}

📦 Spedizione Prime GRATIS
⚠️ Offerta a tempo limitato!"""
    return msg

async def check_offers(context: ContextTypes.DEFAULT_TYPE):
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID non impostato!")
        return
    bot: Bot = context.bot
    for product in WATCHLIST:
        data = await get_amazon_price(product["asin"])
        if data["price"] and data["price"] <= product["max_price"]:
            msg = format_offer_message(product, data["price"], data["original"])
            try:
                await bot.send_message(chat_id=CHANNEL_ID, text=msg)
                logger.info(f"Offerta pubblicata: {product['name']} a {data['price']}€")
            except Exception as e:
                logger.error(f"Errore invio messaggio: {e}")
        await asyncio.sleep(2)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Ciao! Sono Lafabra Bot!\n\n"
        "Monitoro le offerte Amazon e le pubblico automaticamente sul canale.\n\n"
        "Comandi disponibili:\n"
        "/check - Controlla offerte ora\n"
        "/watchlist - Vedi prodotti monitorati\n"
        "/aggiungi ASIN NOME PREZZO_MAX - Aggiungi prodotto\n"
        "/help - Aiuto"
    )

async def check_now(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("🔍 Controllo offerte in corso...")
    for product in WATCHLIST:
        data = await get_amazon_price(product["asin"])
        if data["price"]:
            emoji = "🟢" if data["price"] <= product["max_price"] else "🔴"
            await update.message.reply_text(
                f"{emoji} {product['name']}\n"
                f"💰 Prezzo attuale: {data['price']:.2f}€\n"
                f"🎯 Soglia: {product['max_price']:.2f}€\n"
                f"🔗 {build_affiliate_link(product['asin'])}"
            )
        else:
            await update.message.reply_text(f"⚠️ Impossibile leggere prezzo per {product['name']}")
        await asyncio.sleep(1)

async def watchlist_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not WATCHLIST:
        await update.message.reply_text("📋 Watchlist vuota!")
        return
    msg = "📋 *Prodotti monitorati:*\n\n"
    for i, p in enumerate(WATCHLIST, 1):
        msg += f"{i}. {p['name']}\n   ASIN: {p['asin']}\n   Soglia: {p['max_price']}€\n\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def aggiungi_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "❌ Uso corretto:\n/aggiungi ASIN NOME_PRODOTTO PREZZO_MAX\n\n"
            "Esempio:\n/aggiungi B0BLGJHQLJ Profumo-Khamrah 30.00"
        )
        return
    asin = args[0]
    nome = args[1].replace("-", " ")
    try:
        prezzo = float(args[2])
    except ValueError:
        await update.message.reply_text("❌ Prezzo non valido!")
        return
    WATCHLIST.append({"asin": asin, "name": nome, "max_price": prezzo})
    await update.message.reply_text(
        f"✅ Aggiunto!\n\n"
        f"📦 {nome}\n"
        f"🔑 ASIN: {asin}\n"
        f"🎯 Soglia prezzo: {prezzo}€"
    )

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🤖 *Lafabra Bot - Guida*\n\n"
        "Questo bot monitora i prezzi Amazon e pubblica automaticamente le offerte sul tuo canale Telegram.\n\n"
        "*Comandi:*\n"
        "/start - Avvia il bot\n"
        "/check - Controlla prezzi ora\n"
        "/watchlist - Lista prodotti monitorati\n"
        "/aggiungi ASIN NOME PREZZO - Aggiungi prodotto\n"
        "/help - Questa guida",
        parse_mode="Markdown"
    )

def main():
    app = Application.builder().token(TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("check", check_now))
    app.add_handler(CommandHandler("watchlist", watchlist_cmd))
    app.add_handler(CommandHandler("aggiungi", aggiungi_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.job_queue.run_repeating(check_offers, interval=3600, first=60)
    logger.info("🚀 Lafabra Bot avviato!")
    app.run_polling()

if __name__ == "__main__":
    main()
