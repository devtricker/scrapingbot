import re
import asyncio
import os
import sys

# Windows par event loop ka issue fix karne ke liye import se pehle ye lagana zaruri hai
if sys.platform == 'win32':
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
# Agar event loop set nahi hai to manually set karna padta hai naye python versions me
try:
    asyncio.get_event_loop()
except RuntimeError:
    asyncio.set_event_loop(asyncio.new_event_loop())

from pyrogram import Client, filters
from pyrogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery

# ==========================================
# ⚙️ CONFIGURATION (Yahan apni details dale)
# ==========================================
API_ID = 6  # Official Telegram Android API_ID
API_HASH = "eb06d4abfb49dc3eeb1aeb98ae0f581e"  # Official Telegram Android API_HASH
BOT_TOKEN = "8869647573:AAEBQfRqJaQv0Sdes_IgRlUQwqsivDb6HFk"  # BotFather se mila token dale

# Source channels jaha se cards scrape karne hai (Public username ya Private ID)
# Private channel ka ID hamesha -100 se start hota hai
SOURCE_CHATS = [-1001234567890, "public_channel_username"] 

# Target channel jaha cards send karne hai
TARGET_CHAT = -1003935659203 
# ==========================================

# 🤖 BOT CLIENT (Inline buttons aur commands ke liye)
bot = Client(
    "bot_session",
    api_id=API_ID,
    api_hash=API_HASH,
    bot_token=BOT_TOKEN
)

# 👤 USERBOT CLIENT (Private/Restricted channels se scrape karne ke liye)
userbot = Client(
    "userbot_session",
    api_id=API_ID,
    api_hash=API_HASH
)

def replace_checked_by(text):
    if not text:
        return text
    # Regex pattern jo 'Checked by' ke baad wale naam ko dhoondhega aur replace karega
    pattern = r"(Checked by\s*(?:[^\w\s]+\s*)?)\S+"
    replaced_text = re.sub(pattern, r"\g<1>@DEVTRONEX", text, flags=re.IGNORECASE)
    return replaced_text

# 1️⃣ /start command with Inline Buttons & Back feature
@bot.on_message(filters.command("start") & filters.private)
async def start_command(client, message):
    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🛠 Scraper Settings", callback_data="settings")],
        [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
    ])
    await message.reply_text(
        "👋 **Hello! Main aapka Scraper Bot hu.**\n\n"
        "➤ Main automatically cards scrape kar sakta hu.\n"
        "➤ Aap mujhe kisi restricted post ka link bhej kar uska data nikalwa sakte hai.",
        reply_markup=keyboard
    )

@bot.on_callback_query()
async def callback_handler(client, callback_query: CallbackQuery):
    if callback_query.data == "settings":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ])
        await callback_query.message.edit_text(
            "⚙️ **Settings**\n\n"
            "Source aur Target channels ko aap `bot.py` file me configure kar sakte hai.",
            reply_markup=keyboard
        )
    elif callback_query.data == "help":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔙 Back", callback_data="back_to_main")]
        ])
        await callback_query.message.edit_text(
            "ℹ️ **Help / Features:**\n\n"
            "1. **Auto Scrape:** Bot apne aap source channels se cards scrape karega.\n"
            "2. **Restricted Links:** Koi bhi private channel ka link bheje, bot usko bypass karke content de dega.\n"
            "3. **Custom Tag:** 'Checked by' ko hamesha `@DEVTRONEX` se replace karega.",
            reply_markup=keyboard
        )
    elif callback_query.data == "back_to_main":
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("🛠 Scraper Settings", callback_data="settings")],
            [InlineKeyboardButton("ℹ️ Help", callback_data="help")]
        ])
        await callback_query.message.edit_text(
            "👋 **Hello! Main aapka Scraper Bot hu.**\n\n"
            "➤ Main automatically cards scrape kar sakta hu.\n"
            "➤ Aap mujhe kisi restricted post ka link bhej kar uska data nikalwa sakte hai.",
            reply_markup=keyboard
        )

# 2️⃣ Restricted Post Link se content nikalna (Bypass Restrict Saving Content)
@bot.on_message(filters.regex(r"https://t\.me/(c/)?(.*)/(\d+)") & filters.private)
async def extract_restricted_post(client, message):
    link = message.text.strip()
    match = re.match(r"https://t\.me/(c/)?(.*)/(\d+)", link)
    if not match:
        return
    
    is_private = bool(match.group(1))
    chat_id = match.group(2)
    msg_id = int(match.group(3))
    
    if is_private:
        # Private channels ke ID ke aage -100 lagana padta hai
        if not chat_id.startswith("-100"):
            chat_id = int("-100" + chat_id)
        else:
            chat_id = int(chat_id)
    
    status_msg = await message.reply_text("⏳ Post extract kar raha hu, please wait...")
    
    try:
        # Userbot message fetch karega kyunki wo restricted content bypass kar sakta hai
        msg = await userbot.get_messages(chat_id, msg_id)
        
        if msg.empty:
            await status_msg.edit_text("❌ Message nahi mila. Kya userbot us channel me add hai?")
            return

        text = msg.text or msg.caption or ""
        new_text = replace_checked_by(text)
        
        if msg.photo:
            # Agar image hai, to image ke sath text bhejenge
            if msg.has_protected_content:
                file = await userbot.download_media(msg)
                await message.reply_photo(photo=file, caption=new_text)
                os.remove(file)
            else:
                await message.reply_photo(photo=msg.photo.file_id, caption=new_text)
        elif new_text:
            await message.reply_text(new_text)
        else:
            await status_msg.edit_text("❌ Is message me koi text ya image nahi hai.")
            return
            
        await status_msg.delete()
    except Exception as e:
        await status_msg.edit_text(f"❌ Error: {e}\n\nMake sure Userbot is channel me add hai.")

# 3️⃣ Auto Scraper (Bulk ya Single cards turant scrape karega)
@userbot.on_message(filters.chat(SOURCE_CHATS) & (filters.text | filters.caption))
async def auto_scrape_cards(client, message):
    text = message.text or message.caption
    
    # Check if the message contains card details (Card:, Charged, ya CC format)
    if "Card:" in text or "Charged" in text or re.search(r"\d{15,16}[\s\|-]\d{2}[\s\|-]\d{2,4}", text):
        new_text = replace_checked_by(text)
        
        try:
            if message.photo:
                if message.has_protected_content:
                    file = await userbot.download_media(message)
                    await userbot.send_photo(TARGET_CHAT, photo=file, caption=new_text)
                    os.remove(file)
                else:
                    await userbot.send_photo(TARGET_CHAT, photo=message.photo.file_id, caption=new_text)
            else:
                await userbot.send_message(TARGET_CHAT, text=new_text)
        except Exception as e:
            print(f"Scrape Error: {e}")

# ==========================================
# 🚀 MAIN RUNNER (Dono clients ek sath chalane ke liye)
# ==========================================
async def main():
    print("🤖 Bot start ho raha hai...")
    await bot.start()
    
    print("👤 Userbot start ho raha hai... (Pehli baar login karna pad sakta hai)")
    await userbot.start()
    
    print("✅ Dono successfully chal rahe hai! Press Ctrl+C to stop.")
    
    from pyrogram import idle
    await idle()
    
    await bot.stop()
    await userbot.stop()

if __name__ == "__main__":
    import sys
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
