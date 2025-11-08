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
    print("Error: game_database.py [Response 101] file ကို မတွေ့ပါ။")
    exit()

# --- (အသစ်) Environment Variables (Game Bot အတွက်) ---
try:
    GAME_BOT_TOKEN = os.environ.get("GAME_BOT_TOKEN") 
    OWNER_ID = int(os.environ.get("ADMIN_ID"))
    MONGO_URL = os.environ.get("MONGO_URL") 
    
    if not all([GAME_BOT_TOKEN, OWNER_ID, MONGO_URL]):
        print("Error: Game Bot Environment variables များ (GAME_BOT_TOKEN, ADMIN_ID, MONGO_URL) မပြည့်စုံပါ။")
        exit()

except Exception as e:
    print(f"Error: Environment variables များ load လုပ်ရာတွင် အမှားဖြစ်နေပါသည်: {e}")
    exit()

# --- (ပြင်ဆင်ပြီး) Global Settings ---
SPAWN_MESSAGE_COUNT = 50 # 50 messages to spawn
ANTI_SPAM_LIMIT = 10 # 10 consecutive messages

# In-memory tracking
group_message_counts = {}
# { group_id: 49 }
last_user_tracker = {}
# { group_id: {"user_id": 12345, "count": 9} }
# --- (ပြီး) ---


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
                             f"ဒီ Group မှာ Message 50 ပြည့်တိုင်း Character တွေ ပေါ်လာပါမယ်။\n"
                             f"/catch [name] နဲ့ ဖမ်းနိုင်ပါပြီ။"
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

# --- (အသစ်) Message 50 Logic Handler ---

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Group ထဲက message အားလုံးကို ဖမ်းပြီး 50 ပြည့်မပြည့် စစ်ပါ"""
    
    # Message (သို့) User မပါရင် (Channel post လိုမျိုး) ဆိုရင် ထွက်
    if not update.message or not update.effective_user:
        return
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    # (၁) Group မှာ ဖမ်းစရာ Character ကျန်နေသေးရင် ဘာမှမလုပ်နဲ့
    if gamedb.get_active_spawn(chat_id):
        return
        
    # (၂) Anti-Spam စစ်ဆေးခြင်း (10 messages)
    can_count_message = False
    
    if chat_id not in last_user_tracker:
        # ဒီ Group မှာ ပထမဆုံး စာပို့တာ
        last_user_tracker[chat_id] = {"user_id": user_id, "count": 1}
        can_count_message = True
    elif last_user_tracker[chat_id]["user_id"] == user_id:
        # ပို့တဲ့သူက နောက်ဆုံးလူ ဖြစ်နေရင်
        if last_user_tracker[chat_id]["count"] < ANTI_SPAM_LIMIT:
            # 10 ကြောင်း မပြည့်သေးရင်
            last_user_tracker[chat_id]["count"] += 1
            can_count_message = True
        else:
            # 10 ကြောင်း ပြည့်သွားရင် (ဒီ message ကို မရေတွက်တော့ဘူး)
            can_count_message = False
    else: 
        # နောက်တစ်ယောက် ဝင်ပြောတာ
        last_user_tracker[chat_id] = {"user_id": user_id, "count": 1}
        can_count_message = True
        
    # (၃) Message ကို ရေတွက်ခွင့် မရှိရင် ဒီနေရာမှာတင် ရပ်ပါ
    if not can_count_message:
        return
        
    # (၄) Group Message Count ကို တိုးပါ
    if chat_id not in group_message_counts:
        group_message_counts[chat_id] = 1
    else:
        group_message_counts[chat_id] += 1
        
    # print(f"Group {chat_id} count is now: {group_message_counts[chat_id]}") # (Debug လုပ်ချင်ရင် ဒီ line ကို ဖွင့်ပါ)

    # (၅) 50 ပြည့်မပြည့် စစ်ပါ
    if group_message_counts.get(chat_id, 0) >= SPAWN_MESSAGE_COUNT:
        print(f"Spawning character in Group {chat_id} (Message 50 reached)")
        # Counter တွေ အကုန် Reset လုပ်
        group_message_counts[chat_id] = 0
        last_user_tracker[chat_id] = {}
        
        # --- (Spawn Logic အသစ်) ---
        character = gamedb.get_random_character()
        if not character:
            print("No characters found in DB. Admin က /addchar အရင် သုံးပေးပါ။")
            return
        
        try:
            char_name = character.get("name", "Unknown")
            char_image = character.get("image_url", "")
            
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=char_image,
                caption=f"A CHARACTER HAS SPAWNED! 😱\n\nADD THIS CHARACTER TO YOUR HAREM USING `/catch {char_name}`"
            )
            # DB ထဲမှာ မှတ်ထား
            gamedb.set_active_spawn(chat_id, char_name)
            
        except Exception as e:
            print(f"Error spawning character in group {chat_id}: {e}")

# --- User Commands (မပြောင်းပါ) ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 မင်္ဂလာပါ! Character Catching Bot ပါ။\nGroup တွေထဲမှာ Message 50 ပြည့်တိုင်း Character တွေ ပေါ်လာပါမယ်။\n/catch [name] နဲ့ ဖမ်းနိုင်ပါတယ်။")

async def catch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Character ကို ဖမ်းမယ့် command"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text("❌ /catch command ကို Group တွေထဲမှာပဲ သုံးလို့ရပါတယ်ရှင့်။")
        return

    active_char_name = gamedb.get_active_spawn(chat.id)
    if not active_char_name:
        await update.message.reply_text("😅 ဒီ Group မှာ အခု ဖမ်းစရာ Character မရှိသေးပါဘူးရှင့်။")
        return
        
    try:
        guessed_name = " ".join(context.args)
    except:
        guessed_name = ""
        
    if guessed_name.lower() != active_char_name.lower():
        await update.message.reply_text(f"❌ နာမည် မှားနေပါတယ်ရှင့်! (Hint: `{active_char_name}`)")
        return
        
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

async def wang_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Admin Only) DB ထဲက Character List အားလုံးကို ပြပါ။"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ ဤ command ကို Owner သာ သုံးနိုင်ပါသည်။")
        return

    names_list = gamedb.get_all_character_names() # [Response 102]
    
    if not names_list:
        await update.message.reply_text("ℹ️ Character Database [Response 101] ထဲမှာ ဘာမှ မရှိသေးပါဘူး။\n`/addchar` [Response 101] ကို အရင် သုံးပါ။")
        return

    msg = "📔 **Character Database List** 📔\n\n"
    count = 0
    for name in names_list:
        count += 1
        msg += f"{count}. `{name}`\n"
        
        if len(msg) > 3800:
            await update.message.reply_text(msg, parse_mode="Markdown")
            msg = "" 
            
    if msg: 
        await update.message.reply_text(msg, parse_mode="Markdown")

    await update.message.reply_text(f"✅ စုစုပေါင်း Character `{count}` ကောင် တွေ့ရှိပါသည်။")

# --- Owner Commands (မပြောင်းပါ) ---

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

    # --- (JobQueue (Timer) ကို ဖြုတ်လိုက်ပါပြီ) ---

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("catch", catch_command))
    application.add_handler(CommandHandler("harem", harem_command))
    
    # Owner Command
    application.add_handler(CommandHandler("addchar", add_character_command))
    application.add_handler(CommandHandler("wang", wang_command)) #

    # Group Management
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_chat_member))

    # --- (အသစ်) Message 50 Handler ---
    # Group ထဲက Command မဟုတ်တဲ့ စာသားတွေ (TEXT) အားလုံးကို ဖမ်းပါ
    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND & filters.ChatType.GROUPS, 
        handle_group_message
    ))

    print("🚀 Game Bot အဆင်သင့်ဖြစ်ပါပြီ။ (Message Count Mode)")
    application.run_polling()

if __name__ == "__main__":
    main()
