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

# --- Environment Variables (Game Bot အတွက်) ---
try:
    GAME_BOT_TOKEN = os.environ.get("GAME_BOT_TOKEN") 
    OWNER_ID = int(os.environ.get("OWNER_ID")) # (Response 110 မှာ ပြင်ထား)
    MONGO_URL = os.environ.get("MONGO_URL") 
    
    if not all([GAME_BOT_TOKEN, OWNER_ID, MONGO_URL]):
        print("Error: Game Bot Environment variables များ (GAME_BOT_TOKEN, OWNER_ID, MONGO_URL) မပြည့်စုံပါ။")
        exit()

except Exception as e:
    print(f"Error: Environment variables များ load လုပ်ရာတွင် အမှားဖြစ်နေပါသည်: {e}")
    exit()

# --- Global Settings ---
SPAWN_MESSAGE_COUNT = 100 # 100 messages to spawn
ANTI_SPAM_LIMIT = 8 # 10 consecutive messages

# In-memory tracking
group_message_counts = {}
last_user_tracker = {}


# --- Group Management Handlers ---

async def on_new_chat_members(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot က Group အသစ်ထဲ ဝင်လာရင် Member 100 ရှိမရှိ စစ်ပါ။"""
    me = await context.bot.get_me()
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        for new_member in update.message.new_chat_members:
            if new_member.id == me.id:
                try:
                    # (Response 107 Logic) Member အရေအတွက်ကို စစ်ပါ
                    member_count = await context.bot.get_chat_member_count(chat.id)
                    
                    if member_count < 100: #
                        await context.bot.send_message(
                            chat_id=chat.id,
                            text=f"❌ ဤ Group တွင် Member {member_count} ယောက်သာ ရှိပါသည်။\n"
                                 f"Member 100 ပြည့်သော Group များတွင်သာ ဤ Bot ကို အသုံးပြုနိုင်ပါသည်။\n\n"
                                 f"Bot မှ ယခု Group မှ ပြန်လည် ထွက်ခွာပါမည်။"
                        )
                        await context.bot.leave_chat(chat.id)
                        print(f"Game Bot left group '{chat.title}' (ID: {chat.id}) due to insufficient members (Count: {member_count}).")
                    
                    else:
                        print(f"Game Bot joined a new group: {chat.title} (ID: {chat.id}) (Count: {member_count})")
                        gamedb.add_group(chat.id, chat.title) 
                        await context.bot.send_message(
                            chat_id=chat.id,
                            text=f"👋 မင်္ဂလာပါ! {me.first_name} ပါရှင့်။\n"
                                 f"ဒီ Group မှာ Message 100 ပြည့်တိုင်း Character တွေ ပေါ်လာပါမယ်။\n"
                                 f"/catch [name] နဲ့ ဖမ်းနိုင်ပါပြီ။"
                        )
                        
                except Exception as e:
                    print(f"Error checking member count in new group: {e}")
                    try:
                        await context.bot.leave_chat(chat.id)
                    except:
                        pass

async def on_left_chat_member(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot က Group ကနေ ထွက်သွားရင် DB ကနေ ဖြုတ်ပါ"""
    me = await context.bot.get_me()
    chat = update.effective_chat
    
    if chat.type in ["group", "supergroup"]:
        if update.message.left_chat_member.id == me.id:
            print(f"Game Bot left/was kicked from group: (ID: {chat.id})")
            gamedb.remove_group(chat.id)

# --- (Message 100 Logic) Handler ---

async def handle_group_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Group ထဲက message အားလုံးကို ဖမ်းပြီး 100 ပြည့်မပြည့် စစ်ပါ"""
    if not update.message or not update.effective_user:
        return
        
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    
    if gamedb.get_active_spawn(chat_id):
        return
        
    can_count_message = False
    
    if chat_id not in last_user_tracker:
        last_user_tracker[chat_id] = {"user_id": user_id, "count": 1}
        can_count_message = True
    elif last_user_tracker[chat_id]["user_id"] == user_id:
        if last_user_tracker[chat_id]["count"] < ANTI_SPAM_LIMIT:
            last_user_tracker[chat_id]["count"] += 1
            can_count_message = True
        else:
            can_count_message = False
    else: 
        last_user_tracker[chat_id] = {"user_id": user_id, "count": 1}
        can_count_message = True
        
    if not can_count_message:
        return
        
    if chat_id not in group_message_counts:
        group_message_counts[chat_id] = 1
    else:
        group_message_counts[chat_id] += 1
        
    # (Debug လုပ်ချင်ရင် ဒီ line ကို ဖွင့်ပါ)
    # print(f"Group {chat_id} count: {group_message_counts[chat_id]} / {SPAWN_MESSAGE_COUNT}") 

    if group_message_counts.get(chat_id, 0) >= SPAWN_MESSAGE_COUNT:
        print(f"Spawning character in Group {chat_id} (Message 100 reached)")
        group_message_counts[chat_id] = 0
        last_user_tracker[chat_id] = {}
        
        # --- (Spawn Logic အသစ်) ---
        character_obj = gamedb.get_random_character() # Get the full object
        if not character_obj:
            print("No characters found in DB. Admin က /addchar အရင် သုံးပေးပါ။")
            return
        
        try:
            char_name = character_obj.get("name", "Unknown")
            char_image = character_obj.get("image_url", "")
            
            # --- (ပြင်ဆင်ပြီး) Hint ဖြုတ်ပြီး နာမည်အမှန် ပြန်ထည့် ---
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=char_image,
                caption=f"ᴀ ᴄʜᴀʀᴀᴄᴛᴇʀ ʜᴀꜱ ꜱᴘᴀᴡɴᴇᴅ! 😱\n\nᴀᴅᴅ ᴛʜɪꜱ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ʏᴏᴜʀ ʜᴀʀᴇᴍ ᴜꜱɪɴɢ `/catch [Name]`"
            )
            # DB ထဲမှာ Object တစ်ခုလုံးကို မှတ်ထား
            gamedb.set_active_spawn(chat_id, character_obj) 
            
        except Exception as e:
            print(f"Error spawning character in group {chat_id}: {e}")

# --- User Commands ---

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Bot ကိုစဖွင့်ရင် (ပုံစံအသစ် နဲ့) ကြိုဆိုပါ။"""
    user_name = update.effective_user.first_name
    me = await context.bot.get_me()
    bot_username = me.username
    
    # --- (အသစ်) Buttons ---
    keyboard = [
        [InlineKeyboardButton(
            "✚ ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ✚", 
            url=f"https://t.me/{bot_username}?startgroup=true"
        )],
        [
            InlineKeyboardButton(" ꜱᴜᴘᴘᴏʀᴛ ", url=f"t.me/everythingreset"),
            InlineKeyboardButton(" ᴜᴘᴅᴀᴛᴇꜱ ", url=f"t.me/sasukemusicsupportchat") # (ကိုကို့ Update Channel Link ရှိရင် ဒီမှာ ပြောင်းထည့်ပါ)
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # --- (အသစ်) Message Text ---
    start_msg = (
        f"👋 **Hᴇʏ ᴛʜᴇʀᴇ, {user_name}!**\n\n"
        f"◎ ᴍʏꜱᴇʟꜰ **{me.first_name}**\n"
        f"◎ ɪ ꜱᴘᴀᴡɴ ᴄʜᴀʀᴀᴄᴛᴇʀꜱ ɪɴ ᴄʜᴀᴛꜱ ᴀꜰᴛᴇʀ 100 ᴍᴇꜱꜱᴀɢᴇꜱ ᴀɴᴅ ʟᴇᴛ ᴜꜱᴇʀꜱ ᴄᴀᴛᴄʜ ᴛʜᴇᴍ.\n\n"
        f"ᴀᴅᴅ ᴍᴇ ᴛᴏ ʏᴏᴜʀ ɢʀᴏᴜᴘ ᴀɴᴅ ꜱᴛᴀʀᴛ ᴄᴀᴛᴄʜɪɴɢ!"
    )
    
    await update.message.reply_text(start_msg, reply_markup=reply_markup, parse_mode="Markdown")

async def catch_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Character ကို ဖမ်းမယ့် command (ပြင်ဆင်ပြီး)"""
    user = update.effective_user
    chat = update.effective_chat
    
    if chat.type == "private":
        await update.message.reply_text("❌ /catch command ကို Group တွေထဲမှာပဲ သုံးလို့ရပါတယ်ရှင့်။")
        return

    # (၁) DB ထဲက Character Object အပြည့်အစုံကို ယူပါ
    active_char_obj = gamedb.get_active_spawn(chat.id) 
    
    if not active_char_obj:
        # --- (ပြင်ဆင်ပြီး) "Already Caught" Logic ---
        last_catcher_name = gamedb.get_group_last_catcher(chat.id)
        if last_catcher_name:
            # နောက်ဆုံးဖမ်းထားသူ ရှိရင်၊ "Already Caught" message ပြပါ
            await update.message.reply_text(
                f"🌸 Cʜᴀʀᴀᴄᴛᴇʀ ᴀʟʀᴇᴀᴅʏ ᴄᴀᴜɢʜᴛ ʙʏ\n**{last_catcher_name}**\n\n"
                f"🥤 ᴡᴀɪᴛ ꜰᴏʀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ ᴛᴏ ꜱᴘᴀᴡɴ",
                parse_mode="Markdown"
            )
        else:
            # (ကိုကိုတောင်းဆိုထားသည့်အတိုင်း)
            # Bot စဝင်လာပြီး ဘယ်သူမှ မဖမ်းရသေးရင် (ဒါမှမဟုတ်) Character မရှိသေးရင်
            # ဘာမှ စာမပြန်ဘဲ (Silent) နေပါ
            pass 
        return
        # --- (ပြီး) ---
        
    active_char_name_lower = active_char_obj.get("name_lower", "")
    
    try:
        guessed_name = " ".join(context.args)
    except:
        guessed_name = ""
        
    if guessed_name.lower() != active_char_name_lower:
        # (Response 131 က Hint ဖြုတ်ထားတဲ့ Logic)
        await update.message.reply_text(f"❌ နာမည် မှားနေပါတယ်ရှင့်။")
        return
        
    # (အောင်မြင်သွားပြီ)
    gamedb.catch_character(user.id, user.first_name, active_char_obj) # User DB ထဲ ထည့်
    gamedb.set_active_spawn(chat.id, None) # Group DB ကနေ ရှင်း
    gamedb.set_group_last_catcher(chat.id, user.first_name) # (အသစ်) နောက်ဆုံးဖမ်းသူကို မှတ်
    
    # --- ("Gotcha" Message -) ---
    char_name = active_char_obj.get("name", "Unknown")
    char_rarity = active_char_obj.get("rarity", "N/A")
    char_anime = active_char_obj.get("anime", "Unknown Series")
    char_emoji = active_char_obj.get("emoji", "")
    
    user_harem_count_in_anime = gamedb.get_user_anime_collection_count(user.id, char_anime)
    total_in_anime = gamedb.get_total_anime_collection_count(char_anime)
    
    gotcha_msg = (
        f"🌸 **{user.first_name}, Yᴏᴜ ɢᴏᴛ ᴀ ɴᴇᴡ ᴄʜᴀʀᴀᴄᴛᴇʀ!**\n\n"
        f"🫧 **Nᴀᴍᴇ:** {char_name} [{char_emoji}]\n"
        f"🟠 **𝙍𝘼𝙍𝙄𝙏𝙔:** {char_rarity}\n"
        f"🏖️ **Aɴɪᴍᴇ:** {char_anime} ({user_harem_count_in_anime}/{total_in_anime})\n\n"
        f"❄️ ᴄʜᴇᴄᴋ ʏᴏᴜʀ /harem!"
    )
    
    await update.message.reply_text(gotcha_msg, parse_mode="Markdown")

async def harem_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """ဖမ်းမိထားတဲ့ Character တွေကို ကြည့်ရန် (ပြင်ဆင်ပြီး)"""
    user_id = update.effective_user.id
    my_harem = gamedb.get_user_harem(user_id)
    
    if not my_harem:
        await update.message.reply_text("သင့်မှာ ဖမ်းမိထားတဲ့ Character တစ်ကောင်မှ မရှိသေးပါဘူးရှင့်။")
        return
        
    msg = f"💖 **{update.effective_user.first_name} ၏ Harem Collection** 💖\n\n"
    count = 0
    for char in my_harem:
        count += 1
        name = char.get('character_name', 'N/A')
        emoji = char.get('character_emoji', '')
        rarity = char.get('character_rarity', 'N/A')
        anime = char.get('character_anime', 'N/A')
        
        # (ပြင်ဆင်ပြီး) ပုံစံအလှ
        msg += f"{count}. **{name}** {emoji} (Rarity: {rarity}) - *{anime}*\n"
        
    msg += f"\n**စုစုပေါင်း: {count} ကောင်**"
    await update.message.reply_text(msg, parse_mode="Markdown")

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

# --- Owner Commands ---

async def add_character_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Owner Only) Character အသစ် ထည့်ရန် (ပုံစံအသစ်)"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ Owner သာ သုံးနိုင်ပါသည်။")
        return
    
    # (ပြင်ဆင်ပြီး) "|" separator ကို သုံးပါ
    text = " ".join(context.args)
    parts = text.split('|')
    
    if len(parts) != 5:
        await update.message.reply_text(
            "❌ **Format မှားနေပါပြီ!**\n"
            "`/addchar <Name> | <Image_URL> | <Rarity> | <Anime Series> | <Emoji>`\n\n"
            "**ဥပမာ:**\n"
            "`/addchar Goku | https://i.imgur.com/link.jpg | Rare | Dragon Ball Series | ⚽️`",
            parse_mode="Markdown"
        )
        return
        
    try:
        name = parts[0].strip()
        image_url = parts[1].strip()
        rarity = parts[2].strip()
        anime = parts[3].strip()
        emoji = parts[4].strip()
        
        gamedb.add_character(name, image_url, rarity, anime, emoji)
        
        await update.message.reply_photo(
            photo=image_url,
            caption=f"✅ **Character အသစ် ထည့်ပြီးပါပြီ!**\n\n"
                    f"**Name:** {name} {emoji}\n"
                    f"**Rarity:** {rarity}\n"
                    f"**Anime:** {anime}",
            parse_mode="Markdown"
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Error: {e}")

async def clean_game_db_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """(Owner Only) Game Bot DB [Response 108] အားလုံးကို ဖျက်ပါ။"""
    if update.effective_user.id != OWNER_ID:
        await update.message.reply_text("❌ ဤ command ကို Owner သာ သုံးနိုင်ပါသည်။")
        return

    args = context.args
    
    # --- Confirmation Step ---
    if len(args) == 0 or args[0].lower() != "confirm":
        await update.message.reply_text(
            "🚨 ***CONFIRMATION REQUIRED*** 🚨\n\n"
            "သင် Game Bot (`character.py`) ရဲ့ Database [Response 108] တစ်ခုလုံးကို ဖျက်ရန် ကြိုးစားနေပါသည်။\n\n"
            "Character တွေ၊ User တွေ ဖမ်းထားတာ တွေ အားလုံး ပျက်စီးသွားပါမည်။\n\n"
            "⚠️ **သေချာလျှင်၊ အောက်ပါ command ကို ထပ်မံရိုက်ထည့်ပါ**:\n"
            "`/cleanmongodb confirm`",
            parse_mode="Markdown"
        )
        return

    # --- "/cleanmongodb confirm" ရိုက်ခဲ့လျှင် ---
    await update.message.reply_text("⏳ ***Executing Game DB Wipe...***")
    
    try:
        success = gamedb.wipe_game_data() # DB function အသစ်ကို ခေါ်ပါ
        
        if success:
            await update.message.reply_text(
                "✅ ***SUCCESS*** ✅\n\n"
                "Game Bot Database (`game_bot_db`) [Response 108] တစ်ခုလုံးကို အောင်မြင်စွာ ဖျက်သိမ်းပြီးပါပြီ။\n\n"
                "⚠️ **Bot ကို အခုချက်ချင်း RESTART လုပ်ပါ။**"
            )
        else:
            await update.message.reply_text("❌ ***FAILED***\n\nDatabase ကို ဖျက်ရာတွင် အမှားတစ်ခုခု ဖြစ်ပွားခဲ့သည်။")
    
    except Exception as e:
        await update.message.reply_text(f"❌ ***CRITICAL ERROR***\n\nAn error occurred: {str(e)}")

# --- Main Function ---

def main():
    print("🤖 Game Bot (character.py) စတင်နေပါသည်...")

    application = Application.builder().token(GAME_BOT_TOKEN).build() 

    # --- (JobQueue (Timer) ကို ဖြုတ်ထားပါသည်) ---

    # --- Handlers ---
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("catch", catch_command))
    application.add_handler(CommandHandler("harem", harem_command))
    
    # Owner Command
    application.add_handler(CommandHandler("addchar", add_character_command))
    application.add_handler(CommandHandler("wang", wang_command)) 
    application.add_handler(CommandHandler("cleanmongodb", clean_game_db_command)) 

    # Group Management
    application.add_handler(MessageHandler(filters.StatusUpdate.NEW_CHAT_MEMBERS, on_new_chat_members))
    application.add_handler(MessageHandler(filters.StatusUpdate.LEFT_CHAT_MEMBER, on_left_chat_member))

    # --- (ပြင်ဆင်ပြီး) Message 100 Handler ---
    # filters.TEXT အစား filters.ALL ကို သုံးပြီး အားလုံးကို ရေတွက်ပါ
    application.add_handler(MessageHandler(
        filters.ALL & ~filters.COMMAND & filters.ChatType.GROUPS, 
        handle_group_message
    ))
    # --- (ပြီး) ---

    print("🚀 Game Bot အဆင်သင့်ဖြစ်ပါပြီ။ (Message Count Mode)")
    application.run_polling()

if __name__ == "__main__":
    main()
