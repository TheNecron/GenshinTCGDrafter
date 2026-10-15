import requests
import json
import os
import pandas as pd

def load_json_dict(path):
    if os.path.exists(path) and os.path.getsize(path) > 0:
        with open(path) as f:
            return json.load(f)
    return {}

def load_card_databases():
    url = "https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv"
    characterdb = pd.read_csv(url)
    url = "https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv&gid=864881971"
    equipment_db = pd.read_csv(url)
    url = "https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv&gid=1989525055"
    support_db = pd.read_csv(url)
    url = "https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv&gid=40830628"
    event_db = pd.read_csv(url)
    return characterdb, equipment_db, event_db, support_db

def check_all_cards(action_shareids, character_shareids, manual_overrides):
    characterdb, equipment_db, event_db, support_db = load_card_databases()
    
    # Exclude uncollectible (rating 0) cards - they'll never have a share ID
    equipment_db = equipment_db[equipment_db['Rank'] != 0]
    event_db = event_db[event_db['Rank'] != 0]
    support_db = support_db[support_db['Rank'] != 0]
    
    all_names = set(characterdb['Name']) | set(equipment_db['Name']) | set(event_db['Name']) | set(support_db['Name'])
    known = set(action_shareids.keys()) | set(character_shareids.keys()) | set(manual_overrides.keys())
    
    missing = sorted(all_names - known)
    
    print(f"Total cards/characters: {len(all_names)}")
    print(f"Found: {len(all_names) - len(missing)}")
    print(f"Still missing ({len(missing)}):")
    for name in missing:
        print(f"  {name}")
    
    return missing

def decode_deck_code(code):
    url = f"https://genshin-db-api.vercel.app/api/tcgdeckshare/decode?code={code}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()

def build_reverse_lookup(*dicts):
    reverse = {}
    for d in dicts:
        for name, share_id in d.items():
            reverse[share_id] = name
    return reverse

def find_unknown_ids(code, known_dicts):
    result = decode_deck_code(code)
    share_ids = result["cardshareids"]
    reverse_lookup = build_reverse_lookup(*known_dicts)
    
    print(f"Decoded {len(share_ids)} card IDs from the code:\n")
    unknowns = []
    for share_id in share_ids:
        if share_id in reverse_lookup:
            print(f"  {share_id} -> {reverse_lookup[share_id]}")
        else:
            print(f"  {share_id} -> ??? UNKNOWN - likely your new card")
            unknowns.append(share_id)
    return unknowns

if __name__ == "__main__":
    action_shareids = load_json_dict("action_shareids.json")
    character_shareids = load_json_dict("character_shareids.json")
    manual_overrides = load_json_dict("manual_shareid_overrides.json")
    
    missing = check_all_cards(action_shareids, character_shareids, manual_overrides)
    
    print("\n--- Now paste deck codes to resolve unknown share IDs ---")
    while True:
        code = input("\nPaste the deck code (Ctrl+C to quit): ").strip()
        if not code:
            continue
        
        unknowns = find_unknown_ids(code, [action_shareids, character_shareids, manual_overrides])
        
        if not unknowns:
            print("\nNo unknown IDs found - every card in this deck was already recognized.")
        elif len(unknowns) == 1:
            suggestion = missing[0] if missing else None
            if suggestion:
                prompt = f"\nWhat card is share ID {unknowns[0]}? (type 'y' to confirm it's '{suggestion}'): "
            else:
                prompt = f"\nWhat card is share ID {unknowns[0]}? "
            
            response = input(prompt).strip()
            
            if response.lower() == "y" and suggestion:
                card_name = suggestion
            else:
                card_name = response
            
            manual_overrides[card_name] = unknowns[0]
            with open("manual_shareid_overrides.json", "w") as f:
                json.dump(manual_overrides, f, indent=2)
            print(f"Saved: '{card_name}' -> {unknowns[0]}")
            
            print("\n--- Updated missing-card check ---")
            missing = check_all_cards(action_shareids, character_shareids, manual_overrides)
        else:
            print(f"\n{len(unknowns)} unknown IDs found - narrow down which is which manually:")
            for uid in unknowns:
                print(f"  {uid}")