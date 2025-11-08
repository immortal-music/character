# character.py

import asyncio, os, re, random
from datetime import datetime
from telegram import Update, Bot
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

# Database module (Game Bot အတွက်) ကို import လုပ်ပါ
try:
    import game_database as gamedb
except ImportError:
    print("Error: game_database.py file ကို မတွေ့ပါ။")
    exit()

# --- (အသစ်) Environment Variables (Game Bot အတွက်) ---
try:
    # (BotFather မှာ Bot အသစ်တောင်းပြီး Token အသစ် ထည့်ပါ)
    GAME_BOT_TOKEN = os.environ.get("GAME_BOT_TOKEN") 
    
    # (ကိုကို့ရဲ့ Admin ID)
    OWNER_ID = int(os.environ.get("ADMIN_ID"))
    
    # (DB URL ကတော့ Top-up Bot နဲ့ အတူတူ သုံးလို့ရပါတယ်)
    MONGO_URL = os.environ.get("MONGO_URL") 
    
    if not all([GAME_BOT_TOKEN, OWNER_ID, MONGO_URL]):
        print("Error: Game Bot Environment variables များ (GAME_BOT_TOKEN, ADMIN_ID, MONGO_URL) မပြည့်စုံပါ။")
        exit()

except Exception as e:
    print(f"Error: Environment variables များ load လုပ်ရာတွင် အမှားဖြစ်နေပါသည်: {e}")
    exit()

# --- Global Settings ---
SPAWN_INTERVAL_SECONDS = 3600 # (3600 = ၁ နာရီတစ်ခါ)

# --- Group Management Handlers ---

async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot က Group အသစ်ထဲ ဝင်လာရင် DB ထဲ မှတ်ထားပါ"""
    me = await context.bot.get_me()
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        for new_member in update.message.new_chat_members:
            if new_member.id == me.id:
                print(f"Game Bot joined a new group: {chat.title} (ID: {chat.id})")
                gamedb.add_group(chat.id, chat.title)
                try:
                    await context.bot.send_message(
                        chat_id=chat.id,
                        text=f"👋 မင်္ဂလာပါ! {me.first_name} ပါရှင့်။\n"
                             f"ဒီ Group မှာ Character တွေ ပေါ်လာရင် /catch [name] နဲ့ ဖမ်းနိုင်ပါပြီ။"
                    )
                except Exception as e:
                    print(f"Error sending welcome message to group: {e}")

async def on_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot က Group ကနေ ထွက်သွားရင် DB ကနေ ဖြုတ်ပါ"""
    me = await context.bot.get_me()
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        if update.message.left_chat_member.id == me.id:
            print(f"Game Bot left/was kicked from group: (ID: {chat.id})")
            gamedb.remove_group(chat.id)

# --- Timer Job (Character ပေါ်လာစေရန်) ---

async def spawn_job(context: ContextTypes.DEFAULT_TYPE):
    """Timer ကခေါ်ပြီး Group ထဲမှာ Character ပုံ ပို့မယ့် function"""
    print(f"Running spawn job at {datetime.now()}")
    
    # (၁) DB ထဲက Character တစ်ကောင် ကျပန်း ယူ
    character = gamedb.get_random_character()
    if not character:
        print("No characters found in DB. Admin က /addchar အရင် သုံးပေးပါ။")
        return
        
    # (၂) Bot ရှိနေတဲ့ Group တစ်ခု ကျပန်း ရွေး
    active_groups = gamedb.get_all_groups()
    if not active_groups:
        print("Bot is not in any group.")
        return
    
    target_group_id = random.choice(active_groups)
    
    # (၃) အဲ့ဒီ Group မှာ ဖမ်းစရာ ကျန်နေသေးလား စစ်
    if gamedb.get_active_spawn(target_group_id):
        print(f"Group {target_group_id} မှာ ဖမ်းစရာ ကျန်နေသေးလို့ ဒီတစ်ခါ မပို့တော့ဘူး။")
        return
        
    # (၄) Message ပို့ပြီး DB ထဲမှာ မှတ်ထား
    try:
        char_name = character.get("name", "Unknown")
        char_image = character.get("image_url", "")
        
        await context.bot.send_photo(
            chat_id=target_group_id,
            photo=char_image,
            caption=f"A CHARACTER HAS SPAWNED! 😱\n\nADD THIS CHARACTER TO YOUR HAREM USING `/catch {char_name}`"
        )
        
        # ဒီ Group မှာ ဒီ Character ပေါ်နေပြီလို့ မှတ်ထား
        gamedb.set_active_spawn(target_group_id, char_name)
        print(f"Spawned {char_name} in group {target_group_id}")
        
    except Exception as e:
        print(f"Error spawning character in group {target_group_id}: {e}")

# --- User Commands ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ! Character Catching Bot ပါ။\nGroup တွေထဲမှာ Character တွေ ပေါ်လာဖို့ စောင့်ပြီး /catch လုပ်နိုင်ပါတယ်။")

async def catch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Character ကို ဖမ်းမယ့် command"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text("❌ /catch command ကို Group တွေထဲမှာပဲ သုံးလို့ရပါတယ်ရှင့်။")
        return

    # (၁) Group မှာ ဖမ်းစရာ ရှိမရှိ စစ်
    active_char_name = gamedb.get_active_spawn(chat.id)
    if not active_char_name:
        await update.message.reply_text("😅 ဒီ Group မှာ အခု ဖမ်းစရာ Character မရှိသေးပါဘူးရှင့်။")
        return
        
    # (၂) နာမည် အမှန်ရိုက်မရိုက် စစ်
    try:
        guessed_name = " ".join(context.args)
    except:
        guessed_name = ""
        
    if guessed_name.lower() != active_char_name.lower():
        await update.message.reply_text(f"❌ နာမည် မှားနေပါတယ်ရှင့်! (Hint: `{active_char_name}`)")
        return
        
    # (၃) အောင်မြင်ပါပြီ
    gamedb.catch_character(user.id, user.first_name, active_char_name)
    gamedb.set_active_spawn(chat.id, None) # ဖမ်းပြီးပြီမို့လို့ Group ထဲက ပြန်ဖျက်
    
    await update.message.reply_text(
        f"🎉 **Gotcha!** 🎉\n\n**{user.first_name}** က **{active_char_name}** ကို အောင်မြင်စွာ ဖမ်းမိသွားပါပြီ!"
    )

async def harem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ဖမ်းမိထားတဲ့ Character တွေကို ကြည့်ရန်"""
    user_id = update.effective_user.id
    my_harem = gamedb.get_user_harem(user_id)
    
    if not my_harem:
        await update.message.reply_text("ကိုကို့မှာ ဖမ်းမိထားတဲ့ Character တစ်ကောင်မှ မရှိသေးပါဘူးရှင့်။ 😥")
        return
        
    msg = f"💖 **{update.effective_user.first_name} ၏ Harem Collection** 💖\n\n"
    count = 0
    for char in my_harem:
        count += 1
        msg += f"{count}. **{char.get('character_name')}** (Rarity: {char.get('character_rarity')})\n"
        
    msg += f"\n**စုစုပေါင်း: {count} ကောင်**"
    await update.message.reply_text(msg)

# --- Owner Commands ---

async def add_character_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Owner Only) Character အသစ် ထည့်ရန်"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner သာ သုံးနိုင်ပါသည်။")
        return
        
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("❌ Format မှားနေပါပြီ!\n`/addchar <Rarity> <Image_URL> <Name>`\n\nဥပမာ:\n`/addchar SSR https://i.imgur.com/link.jpg Violet Evergarden`")
        return
        
    try:
        rarity = args[0].upper()
        image_url = args[1]
        name = " ".join(args[2:])
        
        gamedb.add_character(name, image_url, rarity)
        
        await update.message.reply_photo(
            photo=image_url,
            caption=f"✅ **Character အသစ် ထည့်ပြီးပါပြီ!**\n\n"
                    f"**Name:** {name}\n"
                    f"**Rarity:** {rarity}"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

# --- Main Function ---

def main():
    print("🤖 Game Bot (character.py) စတင်နေပါသည်...")

    application = Application.builder().token(GAME_BOT_TOKEN).build() 

    # --- JobQueue (Timer) ကို ဖွင့်ပါ ---
    job_queue = application.job_queue
    job_queue.run_repeating(spawn_job, interval=SPAWN_INTERVAL_SECONDS, first=10) # 10 စက္ကန့်မှာ စ run မယ်

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("catch", catch_command))
    application.add_handler(CommandHandler("harem", harem_command))
    
    # Owner Command
    application.add_handler(CommandHandler("addchar", add_character_command))

    # Group Management
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_chat_member))

    print("🚀 Game Bot အဆင်သင့်ဖြစ်ပါပြီ။")
    application.run_polling()

if __name__ == "__main__":
    main()