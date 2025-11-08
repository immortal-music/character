# game_database.py

import pymongo
import os
from datetime import datetime
import random

# --- MongoDB Connection ---
try:
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
    if not client: return
    active_groups_collection.update_one(
        {"_id": chat_id},
        {"$set": {"name": group_name, "joined_at": datetime.now().isoformat()}},
        upsert=True
    )

def remove_group(chat_id):
    if not client: return
    active_groups_collection.delete_one({"_id": chat_id})

def get_all_groups():
    if not client: return []
    return [doc["_id"] for doc in active_groups_collection.find({}, {"_id": 1})]

# --- Character Management (Admin) ---

def add_character(name, image_url, rarity, anime, emoji):
    """Character အသစ် (Admin က) ထည့်ရန် (Emoji/Anime ပါ)"""
    if not client: return
    characters_collection.update_one(
        {"name_lower": name.lower()},
        {"$set": {
            "name": name,
            "name_lower": name.lower(),
            "image_url": image_url,
            "rarity": rarity,
            "anime": anime, # (အသစ်)
            "emoji": emoji  # (အသစ်)
        }},
        upsert=True
    )

def get_random_character():
    """DB ထဲက Character (Object) တစ်ခုလုံးကို ကျပန်း ဆွဲထုတ်ပါ။"""
    if not client: return None
    all_chars = list(characters_collection.find({}))
    if not all_chars:
        return None
    return random.choice(all_chars)

def get_all_character_names():
    """(ကိုကို့ /wang command အတွက်) DB ထဲက Character နာမည်တွေ အကုန် ယူပါ။"""
    if not client: return []
    try:
        cursor = characters_collection.find({}, {"name": 1, "_id": 0}).sort("name", 1)
        names_list = [doc.get("name") for doc in cursor if doc.get("name")]
        return names_list
    except Exception as e:
        print(f"Error getting all character names: {e}")
        return []

# --- Game Logic Functions ---

def set_active_spawn(group_id, character_object):
    """Group ထဲမှာ ဘယ် character (Object) ပေါ်နေလဲ မှတ်ထားပါ။"""
    if not client: return
    if character_object is None:
        # ဖမ်းမိသွားရင် DB ထဲက ဖျက်ပါ
        group_spawns_collection.delete_one({"_id": group_id})
    else:
        # (ပြင်ဆင်ပြီး) Object တစ်ခုလုံးကို သိမ်းပါ
        group_spawns_collection.update_one(
            {"_id": group_id},
            {"$set": {
                "active_character": character_object, 
                "spawned_at": datetime.now()
            }},
            upsert=True
        )

def get_active_spawn(group_id):
    """Group မှာ ဖမ်းစရာ character (Object) ရှိမရှိ စစ်ပါ။"""
    if not client: return None
    spawn_data = group_spawns_collection.find_one({"_id": group_id})
    return spawn_data.get("active_character") if spawn_data else None # (Object ကို ပြန်ပေး)

def catch_character(user_id, user_name, character_object):
    """User က Character (Object) ကို ဖမ်းမိကြောင်း DB ထဲ မှတ်ပါ။"""
    if not client: return
    if not character_object:
        return 
        
    catch_record = {
        "user_id": user_id,
        "user_name": user_name,
        "character_name": character_object.get("name"),
        "character_image": character_object.get("image_url"),
        "character_rarity": character_object.get("rarity"),
        "character_anime": character_object.get("anime"), # (အသစ်)
        "character_emoji": character_object.get("emoji"), # (အသစ်)
        "caught_at": datetime.now().isoformat()
    }
    user_harems_collection.insert_one(catch_record)

def get_user_harem(user_id):
    """User ဖမ်းမိထားတဲ့ Character list ကို ယူပါ။"""
    if not client: return []
    return list(user_harems_collection.find({"user_id": user_id}).sort("caught_at", -1))
    
def get_user_anime_collection_count(user_id, anime_name):
    """User က ဒီ Anime ထဲက ဘယ်နှစ်ကောင် ဖမ်းပြီးပြီလဲ စစ်ပါ။"""
    if not client: return 0
    return user_harems_collection.count_documents({
        "user_id": user_id, 
        "character_anime": anime_name
    })
    
def get_total_anime_collection_count(anime_name):
    """ဒီ Anime မှာ စုစုပေါင်း Character ဘယ်နှစ်ကောင် ရှိလဲ စစ်ပါ။"""
    if not client: return 0
    return characters_collection.count_documents({"anime": anime_name})
    


def wipe_game_data():
    """
    !!! Game Bot DATA အားလုံးကို ဖျက်ဆီးပါမည် !!!
    """
    if not client:
        return False
    try:
        print("\n" + "="*30)
        print("WARNING: GAME BOT DB WIPE INITIATED...")
        print("="*30 + "\n")
        
        collections_to_wipe = [
            characters_collection,
            user_harems_collection,
            group_spawns_collection,
            active_groups_collection
        ]
        
        for collection in collections_to_wipe:
            collection_name = collection.name
            count = collection.count_documents({})
            collection.delete_many({})
            print(f"WIPED: {collection_name} (Deleted {count} documents)")
            
        print("\n✅ Game Bot collections (4) ခုလုံး ရှင်းလင်းပြီးပါပြီ။")
        return True
    
    except Exception as e:
        print(f"❌ Error during Game Bot wipe: {e}")
        return False
