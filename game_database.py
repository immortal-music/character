# game_database.py

import pymongo
import os
from datetime import datetime
import random

# --- MongoDB Connection ---
try:
    # (Top-up Bot နဲ့ MONGO_URL အတူတူ သုံးလို့ရပါတယ်)
    MONGO_URL = os.environ.get("MONGO_URL")
    if not MONGO_URL:
        print("Error: MONGO_URL environment variable မတွေ့ပါ။")
        exit()
        
    client = pymongo.MongoClient(MONGO_URL)
    db = client["game_bot_db"] # DB အသစ် သီးသန့် သုံးပါ
    
    characters_collection = db["characters"] # Character အားလုံး (Admin ထည့်ရန်)
    user_harems_collection = db["user_harems"]   # User တွေ ဖမ်းမိထားတာ
    group_spawns_collection = db["group_spawns"] # Group မှာ ဘာပေါ်နေလဲ
    active_groups_collection = db["active_groups"] # Bot ရှိနေတဲ့ Group list

    print("✅ Game Bot Database နှင့် အောင်မြင်စွာ ချိတ်ဆက်ပြီးပါပြီ။")
except Exception as e:
    print(f"❌ Game Bot Database ချိတ်ဆက်ရာတွင် Error ဖြစ်နေပါသည်: {e}")
    client = None

# --- Group Management ---

def add_group(chat_id, group_name):
    """Bot ဝင်ထားသော Group ID ကို DB ထဲ မှတ်ထားပါ။"""
    if not client: return
    active_groups_collection.update_one(
        {"_id": chat_id},
        {"$set": {"name": group_name, "joined_at": datetime.now().isoformat()}},
        upsert=True
    )

def remove_group(chat_id):
    """Bot ထွက်သွားသော Group ID ကို DB မှ ဖျက်ပါ။"""
    if not client: return
    active_groups_collection.delete_one({"_id": chat_id})

def get_all_groups():
    """Bot ဝင်ထားသော Group ID များအားလုံးကို ယူပါ။"""
    if not client: return []
    return [doc["_id"] for doc in active_groups_collection.find({}, {"_id": 1})]

# --- Character Management (Admin) ---

def add_character(name, image_url, rarity):
    """Character အသစ် (Admin က) ထည့်ရန်"""
    if not client: return
    characters_collection.update_one(
        {"name_lower": name.lower()},
        {"$set": {
            "name": name,
            "name_lower": name.lower(),
            "image_url": image_url,
            "rarity": rarity
        }},
        upsert=True
    )

def get_random_character():
    """DB ထဲက Character တစ်ကောင်ကို ကျပန်း ဆွဲထုတ်ပါ။"""
    if not client: return None
    all_chars = list(characters_collection.find({}))
    if not all_chars:
        return None
    return random.choice(all_chars)

def get_all_character_names():
    """(ကိုကို့ /wang command အတွက်) DB ထဲက Character နာမည်တွေ အကုန် ယူပါ။"""
    if not client: return []
    try:
        # နာမည်တွေကိုပဲ ဆွဲထုတ်ပြီး A-Z စီ
        cursor = characters_collection.find({}, {"name": 1, "_id": 0}).sort("name", 1)
        names_list = [doc.get("name") for doc in cursor if doc.get("name")]
        return names_list
    except Exception as e:
        print(f"Error getting all character names: {e}")
        return []

# --- Game Logic Functions ---

def set_active_spawn(group_id, character_name):
    """Group ထဲမှာ ဘယ် character ပေါ်နေလဲ မှတ်ထားပါ။"""
    if not client: return
    if character_name is None:
        # ဖမ်းမိသွားရင် DB ထဲက ဖျက်ပါ
        group_spawns_collection.delete_one({"_id": group_id})
    else:
        group_spawns_collection.update_one(
            {"_id": group_id},
            {"$set": {"active_character": character_name.lower(), "spawned_at": datetime.now()}},
            upsert=True
        )

def get_active_spawn(group_id):
    """Group မှာ ဖမ်းစရာ character ရှိမရှိ စစ်ပါ။"""
    if not client: return None
    spawn_data = group_spawns_collection.find_one({"_id": group_id})
    return spawn_data.get("active_character") if spawn_data else None

def catch_character(user_id, user_name, character_name):
    """User က Character ကို ဖမ်းမိကြောင်း DB ထဲ မှတ်ပါ။"""
    if not client: return
    
    # Character ကို DB ထဲက အရင်ရှာ (နာမည်အမှန် ယူဖို့)
    char_data = characters_collection.find_one({"name_lower": character_name.lower()})
    if not char_data:
        return # မရှိတဲ့ Character ဆို မသိမ်းတော့ဘူး
        
    catch_record = {
        "user_id": user_id,
        "user_name": user_name,
        "character_name": char_data.get("name"), # နာမည်အမှန်
        "character_image": char_data.get("image_url"),
        "character_rarity": char_data.get("rarity"),
        "caught_at": datetime.now().isoformat()
    }
    user_harems_collection.insert_one(catch_record)

def get_user_harem(user_id):
    """User ဖမ်းမိထားတဲ့ Character list ကို ယူပါ။"""
    if not client: return []
    return list(user_harems_collection.find({"user_id": user_id}).sort("caught_at", -1))
