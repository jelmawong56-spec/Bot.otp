import logging
import time
import requests
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler, MessageHandler, filters

# ==========================================
# KONFIGURASI - EDIT DUA INI BRO
# ==========================================
TELEGRAM_BOT_TOKEN = "8797712446:AAEp9l5n1dkUqvJQJBhIlqeA1-VU8-BmLhE"
API_KEY_HERO_SMS = "fee69845b1dddA08d3A109598723f997"

# ==========================================
# DATA HARGA
# ==========================================
PRICING = {
    "10": {
        "name": "Vietnam 🇻🇳",
        "tier1": {"price": 0.2, "max_price": 0.2742},
        "tier2": {"price": 0.2742, "max_price": 0.5}
    },
    "4": {
        "name": "Filipina 🇵🇭", 
        "tier1": {"price": 0.14, "max_price": 0.20},
        "tier2": {"price": 0.20, "max_price": 0.24}
    },
    "6": {
        "name": "Indonesia 🇮🇩",
        "tier1": {"price": 0.3, "max_price": 0.5},
        "tier2": {"price": 0.5, "max_price": 0.8}
    },
    "52": {
        "name": "Thailand 🇹🇭",
        "tier1": {"price": 0.25, "max_price": 0.4},
        "tier2": {"price": 0.4, "max_price": 0.6}
    }
}

SERVICES = {
    "wa": "WhatsApp",
    "tg": "Telegram", 
    "go": "Google/Gmail",
    "fb": "Facebook",
    "lf": "TikTok",
    "ig": "Instagram",
    "tw": "Twitter"
}

ORDER_MODES = {
    "min5": {"name": "Minimal 5 nomor", "min": 5, "max": 5},
    "10": {"name": "10 nomor", "min": 10, "max": 10},
    "unlimited": {"name": "♾️ Unlimited (sampe saldo abis)", "min": 1, "max": 99999}
}

INPUT_APIKEY, SELECT_SERVICE, SELECT_COUNTRY, SELECT_PRICE, SELECT_MODE, AUTO_ORDERING = range(6)
user_data = {}

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

class HeroSMS:
    def __init__(self, api_key):
        self.api_key = api_key
        self.base_url = "https://hero-sms.com/stubs/handler_api.php"

    def _request(self, action, params=None):
        if params is None:
            params = {}
        params["api_key"] = self.api_key
        params["action"] = action
        try:
            response = requests.get(self.base_url, params=params, timeout=30)
            return response.text
        except Exception as e:
            return f"ERROR: {str(e)}"

    def get_balance(self):
        res = self._request("getBalance")
        if "ACCESS_BALANCE" in res:
            return float(res.split(":")[1])
        return None

    def get_number(self, service, country, max_price=None):
        params = {"service": service, "country": country}
        if max_price:
            params["maxPrice"] = max_price
        return self._request("getNumber", params)

    def get_status(self, activation_id):
        return self._request("getStatus", {"id": activation_id})

    def set_status(self, activation_id, status):
        return self._request("setStatus", {"id": activation_id, "status": status})

    def check_api_error(self, response):
        if not response:
            return "UNKNOWN_ERROR", "No response from API"
        response_upper = response.upper()
        if "BAD_KEY" in response_upper or "INVALID_API_KEY" in response_upper or "WRONG_API_KEY" in response_upper:
            return "BAD_KEY", "API Key salah atau tidak valid"
        if "LIMIT" in response_upper or "LIMIT_EXCEEDED" in response_upper or "API_LIMIT" in response_upper:
            return "LIMIT_EXCEEDED", "API Key limit reached / terlalu banyak request"
        if "BANNED" in response_upper or "ACCOUNT_BANNED" in response_upper:
            return "BANNED", "Akun di-ban"
        if "NO_MONEY" in response_upper or "NO_BALANCE" in response_upper:
            return "NO_BALANCE", "Saldo habis"
        if "ERROR_SQL" in response_upper or "SQL_ERROR" in response_upper:
            return "API_ERROR", "Error dari server Hero-SMS"
        return None, None

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        del user_data[user_id]
    
    welcome = """🤖 *HERO-SMS AUTO OTP BOT*

⚠️ *WAJIB MASUKIN API KEY HERO-SMS DULU*

Format: `apikey_9bA545256c6A`
(atau langsung: `9bA545256c6A`)

Masukin API Key lu:"""
    await update.message.reply_text(welcome, parse_mode='Markdown')
    return INPUT_APIKEY

async def input_apikey(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    if "apikey_" in text.lower():
        api_key = text.lower().replace("apikey_", "")
    else:
        api_key = text
    
    await update.message.reply_text("⏳ Testing API Key...")
    temp_api = HeroSMS(api_key)
    balance_res = temp_api.get_balance()
    
    error_code, error_msg = temp_api.check_api_error(str(balance_res))
    if error_code:
        error_text = f"""❌ *ERROR API KEY*

_{error_msg}_

Error code: `{error_code}`

Coba:
• Cek ulang API Key dari dashboard Hero-SMS
• Kalau limit, tunggu beberapa menit
• Kalau banned, kontak support Hero-SMS"""
        await update.message.reply_text(error_text, parse_mode='Markdown')
        return INPUT_APIKEY
    
    if balance_res is None:
        await update.message.reply_text("❌ API Key salah atau tidak valid! Coba lagi.")
        return INPUT_APIKEY
    
    user_data[user_id] = {
        "api_key": api_key,
        "api": temp_api,
        "balance": balance_res,
        "monitoring": False
    }
    
    text = f"""✅ *API KEY VALID!*

💰 Saldo: `${balance_res:.4f}`

Pilih menu di bawah:"""
    keyboard = [
        [InlineKeyboardButton("🛒 Mulai Auto-Order", callback_data='menu_buy')],
        [InlineKeyboardButton("💰 Cek Saldo", callback_data='menu_balance')]
    ]
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return ConversationHandler.END

async def buy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in user_data:
        await update.message.reply_text("❌ Masukin API Key dulu! Ketik /start")
        return ConversationHandler.END
    return await show_services(update, context)

async def show_services(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    api = user_data[user_id]["api"]
    balance = api.get_balance()
    
    error_code, error_msg = api.check_api_error(str(balance))
    if error_code:
        await update.message.reply_text(f"❌ {error_msg}\nKetik /start untuk masukin API Key baru.")
        if user_id in user_data:
            del user_data[user_id]
        return ConversationHandler.END
    
    if balance is None:
        await update.message.reply_text("❌ API Key tidak valid lagi. Ketik /start untuk masukin ulang.")
        if user_id in user_data:
            del user_data[user_id]
        return ConversationHandler.END
    
    user_data[user_id]["balance"] = balance
    
    keyboard = []
    row = []
    for i, (code, name) in enumerate(SERVICES.items()):
        row.append(InlineKeyboardButton(name, callback_data=f'service_{code}'))
        if (i + 1) % 2 == 0:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)
    keyboard.append([InlineKeyboardButton("❌ Batal", callback_data='cancel')])
    
    text = f"""🛒 *AUTO-ORDER*

💰 Saldo: `${balance:.4f}`

📱 Pilih Layanan:"""
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
    return SELECT_SERVICE

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    data = query.data
    
    if data == 'menu_buy':
        return await show_services(update, context)
    elif data == 'menu_balance':
        api = user_data[user_id]["api"]
        balance = api.get_balance()
        
        error_code, error_msg = api.check_api_error(str(balance))
        if error_code:
            await query.edit_message_text(f"❌ {error_msg}\nKetik /start untuk masukin API Key baru.")
            if user_id in user_data:
                del user_data[user_id]
            return ConversationHandler.END
        
        await query.edit_message_text(f"💰 Saldo: `${balance:.4f}`", parse_mode='Markdown')
        return
    elif data == 'cancel':
        await query.edit_message_text("❌ Dibatalkan. Ketik /buy untuk mulai lagi.")
        return ConversationHandler.END
    
    if data.startswith('service_'):
        service = data.replace('service_', '')
        user_data[user_id]["service"] = service
        user_data[user_id]["service_name"] = SERVICES[service]
        
        keyboard = []
        for code, info in PRICING.items():
            btn_text = f"{info['name']} (${info['tier1']['price']}/${info['tier2']['price']})"
            keyboard.append([InlineKeyboardButton(btn_text, callback_data=f'country_{code}')])
        keyboard.append([InlineKeyboardButton("🔙 Kembali", callback_data='menu_buy')])
        
        text = f"""📍 *PILIH NEGARA*

Layanan: *{SERVICES[service]}*"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SELECT_COUNTRY
    
    if data.startswith('country_'):
        country = data.replace('country_', '')
        user_data[user_id]["country"] = country
        info = PRICING[country]
        
        keyboard = [
            [InlineKeyboardButton(f"Opsi 1: ${info['tier1']['price']} (max ${info['tier1']['max_price']})", callback_data='price_tier1')],
            [InlineKeyboardButton(f"Opsi 2: ${info['tier2']['price']} (max ${info['tier2']['max_price']})", callback_data='price_tier2')],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"service_{user_data[user_id]['service']}")]
        ]
        
        text = f"""💰 *PILIH HARGA*

Negara: *{info['name']}*
Layanan: *{user_data[user_id]['service_name']}*

• Opsi 1: Murah (stok jarang)
• Opsi 2: Mahal (stok sering)"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SELECT_PRICE
    
    if data.startswith('price_tier'):
        country = user_data[user_id]["country"]
        info = PRICING[country]
        
        if data == 'price_tier1':
            tier = info['tier1']
        else:
            tier = info['tier2']
        
        user_data[user_id]["price"] = tier['price']
        user_data[user_id]["max_price"] = tier['max_price']
        
        keyboard = [
            [InlineKeyboardButton(ORDER_MODES['min5']['name'], callback_data='mode_min5')],
            [InlineKeyboardButton(ORDER_MODES['10']['name'], callback_data='mode_10')],
            [InlineKeyboardButton(ORDER_MODES['unlimited']['name'], callback_data='mode_unlimited')],
            [InlineKeyboardButton("🔙 Kembali", callback_data=f"country_{country}")]
        ]
        
        text = f"""⚙️ *PILIH MODE ORDER*

Harga: `${tier['price']}` per nomor
Saldo: `${user_data[user_id]['balance']:.4f}`

Pilih mode:"""
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return SELECT_MODE
    
    if data.startswith('mode_'):
        mode_key = data.replace('mode_', '')
        mode = ORDER_MODES[mode_key]
        user_data[user_id]["order_mode"] = mode_key
        user_data[user_id]["target_min"] = mode['min']
        user_data[user_id]["target_max"] = mode['max']
        
        balance = user_data[user_id]["balance"]
        price = user_data[user_id]["price"]
        
        if mode_key == 'unlimited':
            quantity = int(balance // price)
            mode_text = "Unlimited (sampe saldo abis)"
        else:
            quantity = mode['max']
            mode_text = mode['name']
        
        min_required = mode['min'] * price
        if balance < min_required:
            await query.edit_message_text(f"❌ Saldo kurang untuk {mode_text}!\nButuh ${min_required:.4f}, saldo ${balance:.4f}")
            return ConversationHandler.END
        
        max_possible = int(balance // price)
        if quantity > max_possible:
            quantity = max_possible
        
        user_data[user_id]["target_quantity"] = quantity
        
        text = f"""⚡ *KONFIRMASI AUTO-ORDER*

💰 Saldo: `${balance:.4f}`
💵 Harga: `${price}`
📦 Target: *{mode_text}*
🔢 Jumlah: *{quantity} nomor*
🌍 {PRICING[user_data[user_id]['country']]['name']}
📱 {user_data[user_id]['service_name']}

Bot akan:
• Refresh tiap 1 detik kalo stok kosong
• Auto-order sampe {quantity} nomor atau saldo habis
• OTP muncul otomatis di chat ini"""
        keyboard = [
            [InlineKeyboardButton(f"✅ MULAI ORDER {quantity} NOMOR", callback_data='start_order')],
            [InlineKeyboardButton("❌ Batal", callback_data='cancel')]
        ]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode='Markdown')
        return AUTO_ORDERING
    
    if data == 'start_order':
        await query.edit_message_text("🚀 *AUTO-ORDER DIMULAI!*\n⏳ Refresh tiap 1 detik...", parse_mode='Markdown')
        asyncio.create_task(auto_order_task(update, context))
        return ConversationHandler.END

async def auto_order_task(update, context):
    user_id = update.effective_user.id
    api = user_data[user_id]["api"]
    service = user_data[user_id]["service"]
    country = user_data[user_id]["country"]
    price = user_data[user_id]["price"]
    max_price = user_data[user_id]["max_price"]
    target_qty = user_data[user_id]["target_quantity"]
    mode = user_data[user_id]["order_mode"]
    chat_id = update.effective_chat.id
    
    orders_placed = 0
    user_data[user_id]["monitoring"] = True
    
    while user_data[user_id].get("monitoring", False):
        if orders_placed >= target_qty:
            await context.bot.send_message(chat_id, f"✅ Target tercapai! Total: {orders_placed} nomor")
            break
        
        current_balance = api.get_balance()
        
        error_code, error_msg = api.check_api_error(str(current_balance))
        if error_code:
            await context.bot.send_message(chat_id, f"❌ {error_msg} ({error_code})\nAuto-order dihentikan.")
            break
        
        if current_balance is None:
            await context.bot.send_message(chat_id, "❌ API Error - tidak bisa cek saldo")
            break
        
        if current_balance < price:
            if orders_placed >= user_data[user_id]["target_min"]:
                await context.bot.send_message(chat_id, f"✅ Minimal tercapai ({orders_placed} nomor). Saldo habis.")
            else:
                await context.bot.send_message(chat_id, f"❌ Saldo habis! Cuma dapet {orders_placed} nomor (target minimal {user_data[user_id]['target_min']})")
            break
        
        res = api.get_number(service, country, max_price)
        
        error_code, error_msg = api.check_api_error(res)
        if error_code:
            if error_code == "LIMIT_EXCEEDED":
                await context.bot.send_message(chat_id, f"⚠️ {error_msg}\nTunggu 30 detik...")
                await asyncio.sleep(30)
                continue
            elif error_code in ["BAD_KEY", "BANNED"]:
                await context.bot.send_message(chat_id, f"❌ {error_msg}\nAuto-order dihentikan.")
                break
            elif error_code == "NO_BALANCE":
                await context.bot.send_message(chat_id, f"⚠️ {error_msg}")
                break
        
        if "ACCESS_NUMBER" in res:
            parts = res.split(":")
            act_id = parts[1]
            phone = parts[2]
            orders_placed += 1
            
            notif = f"""🎉 *NOMOR #{orders_placed}/{target_qty} DIDAPAT!*

📞 `+{phone}`
🆔 `{act_id}`
💰 Sisa: `${api.get_balance():.4f}`

⏳ Tunggu OTP..."""
            await context.bot.send_message(chat_id, notif, parse_mode='Markdown')
            asyncio.create_task(monitor_otp(context, user_id, act_id, chat_id, orders_placed, phone))
            
        elif "NO_NUMBERS" in res:
            if int(time.time()) % 10 == 0:
                try:
                    await context.bot.send_message(chat_id, f"⏳ Stok kosong, retry... ({orders_placed}/{target_qty})")
                except:
                    pass
            await asyncio.sleep(1)
            
        elif "NO_BALANCE" in res:
            await context.bot.send_message(chat_id, "❌ Saldo tidak cukup!")
            break
        else:
            await asyncio.sleep(3)
    
    user_data[user_id]["monitoring"] = False
    await context.bot.send_message(chat_id, f"🏁 Auto-order selesai. Total: {orders_placed} nomor.\nKetik /buy untuk order lagi.")

async def monitor_otp(context, user_id, act_id, chat_id, order_num, phone):
    api = user_data[user_id]["api"]
    start_time = time.time()
    timeout = 1200
    
    while time.time() - start_time < timeout:
        status = api.get_status(act_id)
        
        error_code, error_msg = api.check_api_error(status)
        if error_code and error_code in ["BAD_KEY", "BANNED", "LIMIT_EXCEEDED"]:
            await context.bot.send_message(chat_id, f"❌ Error cek OTP: {error_msg}")
            return
        
        if "STATUS_OK" in status:
            otp = status.split(":")[1]
            text = f"""✅ *OTP NOMOR #{order_num}*

📞 `+{phone}`
🆔 `{act_id}`
🔐 *{otp}*

Selesai!"""
            await context.bot.send_message(chat_id, text, parse_mode='Markdown')
            api.set_status(act_id, 6)
            return
        elif "STATUS_CANCEL" in status:
            await context.bot.send_message(chat_id, f"❌ #{order_num} dibatalkan")
            return
        
        await asyncio.sleep(5)
    
    await context.bot.send_message(chat_id, f"⏰ #{order_num} timeout. Dibatalkan & refund.")
    api.set_status(act_id, 8)

async def stop_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id in user_data:
        user_data[user_id]["monitoring"] = False
    await update.message.reply_text("🛑 Auto-order dihentikan. Ketik /buy untuk mulai lagi.")

# ==========================================
# MAIN - PERHATIKAN KURUNG SIKUNYA
# ==========================================

def main():
    application = Application.builder().token(TELEGRAM_BOT_TOKEN).build()
    
    commands = [
        BotCommand("start", "Masukin API Key"),
        BotCommand("buy", "Mulai auto-order"),
        BotCommand("stop", "Stop auto-order")
    ]
    
    # PERHATIKAN: entry_points HARUS list dengan kurung siku BUKA dan TUTUP
    conv_handler = ConversationHandler(
        entry_points=[
            CommandHandler('start', start),
            CommandHandler('buy', buy_command)
        ],  # <-- INI KURUNG SIKU TUTUPNYA
        states={
            INPUT_APIKEY: [MessageHandler(filters.TEXT & ~filters.COMMAND, input_apikey)],
            SELECT_SERVICE: [CallbackQueryHandler(button_handler)],
            SELECT_COUNTRY: [CallbackQueryHandler(button_handler)],
            SELECT_PRICE: [CallbackQueryHandler(button_handler)],
            SELECT_MODE: [CallbackQueryHandler(button_handler)],
            AUTO_ORDERING: [CallbackQueryHandler(button_handler)]
        },
        fallbacks=[CommandHandler('stop', stop_cmd)],
        per_message=False
    )
    
    application.add_handler(conv_handler)
    application.add_handler(CommandHandler('stop', stop_cmd))
    application.add_handler(CallbackQueryHandler(button_handler))
    
    print("🤖 Bot jalan! Token:", TELEGRAM_BOT_TOKEN[:20] + "...")
    appli