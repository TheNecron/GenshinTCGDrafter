import io, re, requests, random, os, requests, json, subprocess, math, ctypes, traceback, sys, datetime
import tkinter as tk
import pandas as pd
from PIL import Image, ImageTk, ImageDraw, ImageFont

def log_exception_to_file(exc_type, exc_value, exc_tb): #writes exceptions to a log file so can be sent easily to me
    with open("error_log.txt", "w") as f:
        f.write(f"Error occurred at {datetime.datetime.now()}\n\n")
        traceback.print_exception(exc_type, exc_value, exc_tb, file=f)
        
    traceback.print_exception(exc_type, exc_value, exc_tb)  # also print to console, as normal

def tkinter_error_handler(self, exc, val, tb): #catches the actual exception 
    log_exception_to_file(exc, val, tb)

tk.Tk.report_callback_exception = tkinter_error_handler #function call for above


myappid = "GenshinDrafter"
ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
    
ACTION_PATH = "action_shareids.json" 
CHARACTER_PATH = "character_shareids.json"

ELEMENTS = ['Pyro', 'Electro', 'Hydro', 'Cryo', 'Anemo', 'Geo', 'Dendro']

ELEMENT_CONFLICTS = {
    'Pyro': set(),
    'Electro': set(),
    'Hydro': set(),
    'Geo': {'Dendro', 'Anemo'},
    'Anemo': {'Dendro', 'Geo'},
    'Dendro': {'Geo', 'Anemo', 'Cryo'},
    'Cryo': {'Dendro'},
}

RESONANCE_ELEMENT_MAP = {
    "Elemental Resonance: Enduring Rock": "Geo",
    "Elemental Resonance: Fervent Flames": "Pyro",
    "Elemental Resonance: High Voltage": "Electro",
    "Elemental Resonance: Impetuous Winds": "Anemo",
    "Elemental Resonance: Shattering Ice": "Cryo",
    "Elemental Resonance: Soothing Water": "Hydro",
    "Elemental Resonance: Sprawling Greenery": "Dendro",
    "Elemental Resonance: Woven Flames": "Pyro",
    "Elemental Resonance: Woven Ice": "Cryo",
    "Elemental Resonance: Woven Stone": "Geo",
    "Elemental Resonance: Woven Thunder": "Electro",
    "Elemental Resonance: Woven Waters": "Hydro",
    "Elemental Resonance: Woven Weeds": "Dendro",
    "Elemental Resonance: Woven Winds": "Anemo",
}

BURNING_ARTIFACTS = {"Crownless Crown", "Unfinished Reverie"}
MULTI_CONDITION_CARDS = {"Eremite Teatime", "The Narzissenkreuz Adventure"}

FILLER_CHARACTERS = ["Ganyu", "Diona", "Kaeya"] # they fill in if a share-id isnt found to not break deck

DICE_ICON_DIR = "dice_icons"
dice_icons = {}

TAG_ICON_DIR = "tag_icons"
tag_icon_images = {}       # normal color
tag_icon_images_dep = {}   # yellow-tinted, for dependent tags
rating_labels = []
tag_icon_canvases = []
tag_tooltips = []
TAG_DESCRIPTIONS = {
    "Discard": "",
    "Prepare": "",
    "Summon": "",
    "Heal": "",
    "Shield": "",
    "Nightsoul": "",
    "Technique": "",
    "Physical": "",
    "Random": "",
    "Energy": "",
    "Adventure": "",
    "Simulanka": "",
    "Basic Attack": "",
    "Artifacts": "",
    "Weapons": "",
    "Talent": "",
    "Food": "",
    "Location": "",
    "Companion": "",
}

RATING_COLORS = {1: "#8B0000", 2: "#E06666", 3: "#CCCCCC", 4: "#93C47D", 5: "#38761D"}
DEPENDENT_EXPLANATION = "Dependent: this card's effect and offer rate scales heavily with how many cards of this theme are in your deck."
RATING_STRENGTH = {1: 0.25, 2: 0.5, 3: 1.0, 4: 2.0, 5: 4.0} # describes exponential differnces in rating
RATING_TARGET = 3.0 #aims for an average of this... since ratings are 1-5 this is 3 by default for a flat average deck
RATING_SOFTNESS = 0.25  # tune this - higher = stronger pull
# Symmetric hump centered on 3: each step away from 3 halves the desired share for offer rate based on rating distribution
DESIRED_SHARE = {r: 0.5 ** abs(r - 3) for r in [1, 2, 3, 4, 5]}
_total_desired = sum(DESIRED_SHARE.values())
DESIRED_SHARE = {r: v / _total_desired for r, v in DESIRED_SHARE.items()}
CHAR_REACTION_MULT = 3
STICKINESS = 5  # how many "cards worth" a character pick counts as in the running average
RATING_SCALE_EXPLANATION = (
    "Cards are rated on a 1-5 scale based on percieved strength\n"
    "Selecting higher rated cards increases the likelihood of being offered lower rated cards and "
    "vice versa. Note that the scale is exponential, so the impact of selecting a 5 rated card is "
    "twice that of a 4, and the same applies for 1 rated cards compared to 2 rated cards. Characters "
    " ratings are also factored 10x and influenced by rating 3x as much."
)
RATING_BG_IMAGE_PATH = os.path.join(TAG_ICON_DIR, "RatingBG.webp")  # swap in your actual filename
rating_bg_image = None
rating_bg_image_2x = None
rating_text_cache = {}
avg_rating_text_cache = {}

class ToolTip:
    """A small popup that follows the mouse, showing text on hover. Supports *bold* markdown-style formatting."""
    def __init__(self, widget):
        self.widget = widget
        self.tip_window = None
        self.text = ""
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)
        widget.bind("<Motion>", self.move)
    


    def show(self, event=None):
        if not self.text or self.tip_window:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
        self.tip_window = tk.Toplevel(self.widget)
        self.tip_window.wm_overrideredirect(True)
        self.tip_window.wm_geometry(f"+{x}+{y}")
        
        text_widget = tk.Text(self.tip_window, bg="#222222", fg="white", font=("Arial", 10),
                               wrap="word", width=36, height=1, padx=8, pady=6,
                               relief="solid", borderwidth=1, cursor="arrow")
        text_widget.tag_configure("bold", font=("Arial", 10, "bold"))
        
        self._insert_formatted(text_widget, self.text)
        text_widget.config(state="disabled")
        text_widget.pack()
        
        self.tip_window.update_idletasks()
        
        # Grow the box one line at a time until the last character is actually visible
        height = 1
        while text_widget.dlineinfo("end-1c") is None and height < 30:
            height += 1
            text_widget.config(height=height)
            self.tip_window.update_idletasks()
        
        req_width = self.tip_window.winfo_reqwidth()
        req_height = self.tip_window.winfo_reqheight()
        self.tip_window.wm_geometry(f"{req_width}x{req_height}+{x}+{y}")
            
    def _insert_formatted(self, text_widget, text):
        """Splits on *bold* markers and inserts each segment with the right tag."""
        parts = re.split(r'(\*[^*]+\*)', text)
        for part in parts:
            if part.startswith('*') and part.endswith('*') and len(part) > 1:
                text_widget.insert("end", part[1:-1], "bold")
            else:
                text_widget.insert("end", part)
        
    def hide(self, event=None):
        if self.tip_window:
            self.tip_window.destroy()
            self.tip_window = None
    
    def move(self, event=None):
        if self.tip_window:
            x = self.widget.winfo_rootx() + 20
            y = self.widget.winfo_rooty() + self.widget.winfo_height() + 10
            self.tip_window.wm_geometry(f"+{x}+{y}")
    
    def set_text(self, text):
        self.text = text

def build_tag_tooltip_text(regular_tags, dependent_tags):
    lines = [tag for tag in regular_tags]
    lines += [f"{tag} Dependent" for tag in dependent_tags]
    if dependent_tags:
        lines.append("")  # blank line separator
        lines.append(DEPENDENT_EXPLANATION)
    return "\n".join(lines)

def tint_icon(img, color=(255, 215, 0)):
    """Applies a color tint to a (presumably white/light) icon while preserving its alpha shape."""
    img = img.convert("RGBA")
    r, g, b, a = img.split()
    gray = Image.merge("RGB", (r, g, b)).convert("L")
    tinted = Image.merge("RGBA", (
        gray.point(lambda p: p * color[0] // 255),
        gray.point(lambda p: p * color[1] // 255),
        gray.point(lambda p: p * color[2] // 255),
        a
    ))
    return tinted

def make_hex_frame(size, border_width=5):
    """Generates the gold beveled hexagon border, since it's not a separate wiki asset."""
    img = Image.new('RGBA', (size, size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    cx, cy = size / 2, size / 2
    r = size / 2 - 1
    points = []
    for i in range(6):
        angle = math.pi / 2 + i * math.pi / 3
        points.append((cx + r * math.cos(angle), cy + r * math.sin(angle)))
    draw.polygon(points, outline=(193, 175, 144, 255), width=border_width)  # less saturated, darker
    draw.polygon(points, outline=(103, 85, 58, 255), width=1)               # darker inner line too
    return img

def load_dice_icons():
    global dice_icon_images
    dice_icon_images = {}
    NO_FRAME_TYPES = {"Energy", "ArcaneLegend"}
    
    for filename in os.listdir(DICE_ICON_DIR):
        if filename.lower().endswith(".webp"):
            type_name = filename[:-5]
            img = Image.open(os.path.join(DICE_ICON_DIR, filename)).convert("RGBA")
            if type_name in NO_FRAME_TYPES:
                dice_icon_images[type_name] = img  # no frame composited
            else:
                frame = make_hex_frame(img.size[0])
                dice_icon_images[type_name] = Image.alpha_composite(img, frame)

def load_tag_icons():
    for filename in os.listdir(TAG_ICON_DIR):
        if filename.lower().endswith((".png", ".webp")):
            tag_name = os.path.splitext(filename)[0]
            img = Image.open(os.path.join(TAG_ICON_DIR, filename)).convert("RGBA")
            tag_icon_images[tag_name] = img
            tag_icon_images_dep[tag_name] = tint_icon(img)

def load_rating_bg():
    global rating_bg_image, rating_bg_image_2x
    img = Image.open(RATING_BG_IMAGE_PATH).convert("RGBA")
    
    def fit_to_box(source_img, box_size):
        ratio = min(box_size[0] / source_img.width, box_size[1] / source_img.height)
        new_size = (int(source_img.width * ratio), int(source_img.height * ratio))
        resized = source_img.resize(new_size, Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", box_size, (0, 0, 0, 0))
        offset = ((box_size[0] - new_size[0]) // 2, (box_size[1] - new_size[1]) // 2)
        canvas.paste(resized, offset, resized)
        return canvas
    
    rating_bg_image = ImageTk.PhotoImage(fit_to_box(img, (32, 32)))
    rating_bg_image_2x = ImageTk.PhotoImage(fit_to_box(img, (64, 64)))
    
composite_cache = {}  # (type_name, number) -> PhotoImage, so we don't redraw the same combo twice

def get_die_composite(type_name, number_text):
    key = (type_name, number_text)
    if key in composite_cache:
        return composite_cache[key]
    
    base = dice_icon_images.get(type_name)
    if base is None:
        return None
    
    composite = base.copy()
    
    if number_text:  # skip text drawing entirely for Arcane Legend's blank badge
        draw = ImageDraw.Draw(composite)
        size = composite.size[0]
        font = ImageFont.truetype("arialbd.ttf", size=int(size * 0.675))
        text = str(number_text)
        bbox = draw.textbbox((0, 0), text, font=font)
        x = (size - (bbox[2] - bbox[0])) / 2 - bbox[0]
        y = (size - (bbox[3] - bbox[1])) / 2 - bbox[1]
        draw.text((x, y), text, font=font, fill="white", stroke_width=1, stroke_fill="black")
    
    photo = ImageTk.PhotoImage(composite)
    composite_cache[key] = photo
    return photo

def get_avg_rating_text_image(avg_value):
    key = round(avg_value, 2)
    if key in avg_rating_text_cache:
        return avg_rating_text_cache[key]
    
    color_key = max(1, min(5, round(avg_value)))
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arialbd.ttf", size=20)
    text = f"{avg_value:.2f}"
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (64 - (bbox[2] - bbox[0])) / 2 - bbox[0] - 4
    y = (64 - (bbox[3] - bbox[1])) / 2 - bbox[1] + 2
    
    draw.text((x, y), text, font=font, fill=RATING_COLORS.get(color_key, "white"),
               stroke_width=2, stroke_fill="black")
    
    photo = ImageTk.PhotoImage(img)
    avg_rating_text_cache[key] = photo
    return photo

def get_rating_text_image(rating):
    key = rating
    if key in rating_text_cache:
        return rating_text_cache[key]
    
    img = Image.new("RGBA", (32, 32), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = ImageFont.truetype("arialbd.ttf", size=21)
    text = str(rating)
    bbox = draw.textbbox((0, 0), text, font=font)
    x = (32 - (bbox[2] - bbox[0])) / 2 - bbox[0]
    y = (32 - (bbox[3] - bbox[1])) / 2 - bbox[1]
    
    draw.text((x, y), text, font=font, fill=RATING_COLORS.get(rating, "white"),
               stroke_width=1, stroke_fill="black")
    
    photo = ImageTk.PhotoImage(img)
    rating_text_cache[key] = photo
    return photo

theme_tracker_frame = None
theme_avg_canvas = None
theme_tag_widgets = {}  # tag_name -> (canvas, count_label)
    
def update_theme_tracker():
    theme_avg_canvas.delete("all")
    if rating_history:
        total_w = sum(w for _, w in rating_history)
        avg = sum(r * w for r, w in rating_history) / total_w
    else:
        avg = RATING_TARGET
    if rating_bg_image_2x:
        theme_avg_canvas.create_image(0, 0, anchor="nw", image=rating_bg_image_2x)
    theme_avg_canvas.create_image(4, 0, anchor="nw", image=get_avg_rating_text_image(avg))
    
    for tag, count in tag_counts.items():
        if tag not in theme_tag_widgets:
            wrapper = tk.Frame(theme_tracker_frame, bg="black")
            wrapper.pack(side="left", padx=6)
            
            icon_canvas = tk.Canvas(wrapper, width=32, height=32, bg="black", highlightthickness=0)
            icon_canvas.pack()
            icon = tag_icon_images.get(tag)
            if icon:
                photo = ImageTk.PhotoImage(icon.resize((28, 28)))
                icon_canvas.create_image(2, 2, anchor="nw", image=photo)
                icon_canvas.image_ref = photo
            
            tooltip = ToolTip(icon_canvas)
            tooltip.set_text(TAG_DESCRIPTIONS.get(tag, tag))
            
            count_label = tk.Label(wrapper, bg="black", fg="white", font=("Arial", 11, "bold"))
            count_label.pack()
            
            theme_tag_widgets[tag] = (wrapper, count_label, tooltip)
        
        theme_tag_widgets[tag][1].config(text=str(count))
    
#imports from my google sheet the imported wiki data for all cards
url = f"https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv"
characterdb = pd.read_csv(url)
url = f"https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv&gid=864881971"
equipment_db = pd.read_csv(url)
url = f"https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv&gid=1989525055"
support_db = pd.read_csv(url)
url = f"https://docs.google.com/spreadsheets/d/1bbxcREBPb2HBKr_eMriuG_T1JdQmABnVpNKHeUhkSvk/export?format=csv&gid=40830628"
event_db = pd.read_csv(url)

OVERRIDE_PATH = "manual_shareid_overrides.json"

for df in [characterdb, equipment_db, event_db, support_db]: #any unrated card gets a 3 to prevent crashes
    rating_col = 'Rank' 
    df[rating_col] = df[rating_col].fillna(3)

def load_overrides():
    if os.path.exists(OVERRIDE_PATH):
        with open(OVERRIDE_PATH) as f:
            return json.load(f)
    return {}

manual_overrides = load_overrides()

def load_shareid_dicts(): #loads cached pool of json data that includes their shareid for deckcode gen
    with open(ACTION_PATH) as f:
        actions = json.load(f)
    with open(CHARACTER_PATH) as f:
        characters = json.load(f)
    return actions, characters
    
action_shareids, character_shareids = load_shareid_dicts()
_refresh_attempted = False

def run_refresh_with_indicator(): #tries to manually update shareid dicts from API on failure using script
    """Shows a small status label over the main window while the refresh script runs."""
    status_label = tk.Label(root, text="Checking for new cards...", font=("Arial", 14), fg="white", bg="black")
    status_label.grid(row=0, column=0, columnspan=3, pady=20)
    root.update()
    
    try:
        subprocess.run(["python", "refresh_shareids.py"], check=True, timeout=180)
        success = True
    except Exception as e:
        print(f"Refresh failed: {e}")
        success = False
    
    status_label.grid_forget()
    return success

def get_share_id(card_name):
    global action_shareids, character_shareids, manual_overrides
    
    if card_name in manual_overrides:
        return manual_overrides[card_name]
    if card_name in character_shareids:
        return character_shareids[card_name]
    if card_name in action_shareids:
        return action_shareids[card_name]
    
    print(f"Could not find share ID for '{card_name}' - add it to {OVERRIDE_PATH} manually")
    return None
 
def sanitize_dataframe(df):
    """Replaces newlines with spaces, collapses multiple spaces into one, strips extra whitespace."""
    for col in df.select_dtypes(include='object').columns:
        df[col] = (
            df[col]
            .str.replace('\n', ' ', regex=False)
            .str.replace(r'\s+', ' ', regex=True)  # collapse any run of whitespace into a single space
            .str.strip()
        )
    return df

characterdb = sanitize_dataframe(characterdb)
equipment_db = sanitize_dataframe(equipment_db)
event_db = sanitize_dataframe(event_db)
support_db = sanitize_dataframe(support_db)

def filter_uncollectible(df):
    """Removes any row where Rating is 0 (uncollectible/posterity-only cards)."""
    return df[df["Rank"] != 0]

equipment_db = filter_uncollectible(equipment_db)
event_db = filter_uncollectible(event_db)
support_db = filter_uncollectible(support_db)

def parse_tag_list(cell): #parses the lists of tags into their own individual things
    if pd.isna(cell) or not str(cell).strip():
        return []
    return [t.strip() for t in str(cell).split(",") if t.strip()]
    
characterdb['TagList'] = characterdb['Tags'].apply(parse_tag_list)
characterdb['DependentTagList'] = characterdb['Dependent Tags'].apply(parse_tag_list)

def update_tag_counts(row, is_character):
    weight = STICKINESS if is_character else 1
    all_tags = set(row['TagList']) | set(row['DependentTagList'])
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + weight

def group_starts_with(group_value, prefix):
    """Safely checks if a Group value starts with prefix, treating NaN/missing as False."""
    # my lil helper function C: 
    return isinstance(group_value, str) and group_value.startswith(prefix)

def find_talent_matches(description, character_names):
    """Returns ALL matching names (not just single-match), so we can distinguish 0 vs 1 vs multiple."""
    matches = []
    for name in character_names:
        pattern = r'\b' + re.escape(name) + r'\b'
        if re.search(pattern, description):
            matches.append(name)
    return matches

def audit_talent_cards(talent_cards, character_names):
    matched = []
    unmatched = []
    ambiguous = []
    
    for _, row in talent_cards.iterrows():
        card_name = row['Name']  # adjust to your actual column name
        description = row['Effect']   # adjust to your actual column name
        
        matches = find_talent_matches(description, character_names)
        
        if len(matches) == 1:
            matched.append((card_name, matches[0]))
        elif len(matches) == 0:
            unmatched.append(card_name)
        else:
            ambiguous.append((card_name, matches))
    
    print(f"\n=== MATCHED ({len(matched)}) ===")
    for card_name, owner in matched:
        print(f"  {card_name} -> {owner}")
    
    print(f"\n=== UNMATCHED - no character name found ({len(unmatched)}) ===")
    for card_name in unmatched:
        print(f"  {card_name}")
    
    print(f"\n=== AMBIGUOUS - multiple names found ({len(ambiguous)}) ===")
    for card_name, names in ambiguous:
        print(f"  {card_name} -> {names}")
    
    return matched, unmatched, ambiguous

event_talent_cards = event_db[event_db['Group'].str.startswith("Talent")]  # adjust column/filter as needed
matched_events, unmatched_events, ambiguous_events = audit_talent_cards(event_talent_cards, characterdb['Name'].tolist())
talent_cards = equipment_db[equipment_db['Group'].isin(["Talent", "Talent Combat Action"])]
matched, unmatched, ambiguous = audit_talent_cards(talent_cards, characterdb['Name'].tolist())

talent_owner_map = dict(matched)  # from equipment_db audit
talent_owner_map.update(dict(matched_events))  # from event_db audit, once run
# manually add the exceptions
talent_owner_map["Night Realm's Gift: Heart of Unity"] = "Kachina" 

matched_owners = set(talent_owner_map.values())
all_characters = set(characterdb['Name'])
missing_talent = all_characters - matched_owners

print(f"Characters still missing a talent card ({len(missing_talent)}):")

for name in sorted(missing_talent):
    print(f"  {name}")

for card, owner in sorted(talent_owner_map.items(), key=lambda x: x[1]):
    print(f"{owner}: {card}")

def find_artifact_element(description, elements):
    matches = [el for el in elements if re.search(r'\b' + re.escape(el) + r'\b', description)]
    return matches[0] if len(matches) == 1 else None
    
def find_faction_requirement(description):
    if description == "Attach *Cost Reduction* to 1 random card in your Hand and the top card in your Deck.":
        return "Nod-Krai"  # hardcoded exception: Moonsign: Ascendant Gleam, mistagged as Elemental Resonance
    if description.startswith("Target a friendly Monster character and increase its DMG by 1"):
        return "Monster"  # hardcoded exception: Lil' Fungi's Fun-Tastic Fiesta, non-standard wording
    match = re.search(r'at least 2 ([\w\-]+) characters in your deck', description)
    return match.group(1) if match else None

def count_synergy_conditions():
    same_element = any(c >= 2 for c in element_counts.values())
    selected_weapons = characterdb.loc[characterdb['Name'].isin(decklist[:3]), 'Weapon']
    same_weapon = selected_weapons.duplicated().any()
    same_faction = any(c >= 2 for c in faction_counts.values())
    return sum([same_element, same_weapon, same_faction])

def three_unique_elements():
    return len(element_counts) == 3

def netochka_condition_met():
    nod_krai_elements = characterdb.loc[
        (characterdb['Name'].isin(decklist[:3])) & (characterdb['Faction'] == "Nod-Krai"),
        'Element'
    ]
    return nod_krai_elements.nunique() >= 2

def get_card_tags(name):
    if card_pool is None:
        return [], []
    row = card_pool.loc[card_pool['Name'] == name]
    if row.empty:
        return [], []
    return row['TagList'].iloc[0], row['DependentTagList'].iloc[0]

def weighted_avg(history):
    total_w = sum(w for _, w in history)
    if total_w == 0:
        return RATING_TARGET
    return sum(r * w for r, w in history) / total_w

def compute_rating_weights(pool, history, is_character):
    reaction_mult = CHAR_REACTION_MULT if is_character else 1
    avg_so_far = weighted_avg(history) if history else RATING_TARGET
    deviation = avg_so_far - RATING_TARGET
    rating_pop = pool['Rank'].value_counts()
    total_pop = rating_pop.sum()

    def weight_for(r):
        strength = RATING_STRENGTH.get(r, 1.0)
        centered = strength - 1.0
        mean_reversion = math.exp(-RATING_SOFTNESS * reaction_mult * deviation * centered)
        actual_share = rating_pop.get(r, 1) / total_pop
        norm_factor = DESIRED_SHARE[r] / actual_share
        return mean_reversion * norm_factor
    return pool['Rank'].apply(weight_for)
        
def ramp(count, cap=8, low=0.75, high=2.0):  
    return low + (high - low) * min(count, cap) / cap

def dependent_ramp(count, cap=8, low=0.5, high=4.0):
    return low + (high - low) * min(count, cap) / cap

def compute_tag_weights(pool):
    # population of each tag within the CURRENT valid pool
    tag_pop = {}
    for tags in pool['TagList']:
        for t in tags:
            tag_pop[t] = tag_pop.get(t, 0) + 1
    for tags in pool['DependentTagList']:
        for t in tags:
            tag_pop[t] = tag_pop.get(t, 0) + 1
    mean_tag_pop = (sum(tag_pop.values()) / len(tag_pop)) if tag_pop else 1

    def weight_for(row):
        mult = 1.0
        for t in row['TagList']:
            norm = mean_tag_pop / tag_pop.get(t, 1)
            mult *= ramp(tag_counts.get(t, 0)) * norm
        for t in row['DependentTagList']:
            norm = mean_tag_pop / tag_pop.get(t, 1)
            mult *= dependent_ramp(tag_counts.get(t, 0)) * norm
        return max(mult, 0.05)

    return pool.apply(weight_for, axis=1)

def build_card_pool():
    equipment_db['SourcePool'] = "Equipment"
    event_db['SourcePool'] = "Event"
    support_db['SourcePool'] = "Support"
    
    combined = pd.concat([equipment_db, event_db, support_db], ignore_index=True)
    
    # Tag ownership/requirements once, up front, rather than recomputing every round
    combined['TalentOwner'] = combined['Name'].map(talent_owner_map)
    combined['ArtifactElement'] = combined.apply(
        lambda row: find_artifact_element(row['Effect'], ELEMENTS) if row['Group'] == "Artifact" else None,
        axis=1
    )
    combined['ResonanceElement'] = combined['Name'].map(RESONANCE_ELEMENT_MAP)
    combined['FactionRequirement'] = combined.apply(
        lambda row: find_faction_requirement(row['Effect']), axis=1
    )
    combined['TransfigElements'] = combined.apply(
    lambda row: [el for el in ELEMENTS if re.search(r'\b' + re.escape(el) + r'\b', row['Effect'])]
                if row['Name'].startswith("Elemental Transfiguration") else None,
    axis=1
    )
    
    combined['TagList'] = combined['Tags'].apply(parse_tag_list)
    combined['DependentTagList'] = combined['Dependent Tags'].apply(parse_tag_list)
    
    return combined

def get_valid_card_pool():
    selected_weapon_types = set(characterdb.loc[characterdb['Name'].isin(decklist), 'Weapon'])
    allowed_weapon_groups = {f"Weapon {w}" for w in selected_weapon_types}
    qualifying_elements = {el for el, c in element_counts.items() if c >= 2}
    qualifying_elements_1plus = {el for el, c in element_counts.items() if c >= 1}
    qualifying_factions = {f for f, c in faction_counts.items() if c >= 2}
    
    pool = card_pool.copy()
    
    # Weapon type filter
    pool = pool[
        (~pool['Group'].str.startswith("Weapon ")) |
        (pool['Group'].isin(allowed_weapon_groups))
    ]
    
    # Talent ownership filter
    pool = pool[
        (~pool['Group'].str.startswith("Talent")) |
        (pool['TalentOwner'].isin(decklist))
    ]
    
    # Elemental artifact filter (1+ of that element required)
    pool = pool[
        (pool['Group'] != "Artifact") |
        (pool['ArtifactElement'].isna()) |
        (pool['ArtifactElement'].isin(qualifying_elements_1plus))
    ]
    
    # Elemental resonance filter (2+ required), with the manual pass-through exception
    pool = pool[
        (pool['Name'] == "Moonsign: Ascendant Gleam") |
        (pool['ResonanceElement'].isna()) |
        (pool['ResonanceElement'].isin(qualifying_elements))
    ]
    
    # Faction requirement filter (2+ required)
    pool = pool[
        (pool['FactionRequirement'].isna()) |
        (pool['FactionRequirement'].isin(qualifying_factions))
    ]
    
    # Arcane Legend: only 1 allowed total
    if arcane_legend_selected:
        pool = pool[pool['Group'] != "Arcane Legend"]
    
    # Already-picked twice cards can't reappear
    pool = pool[pool['Name'].map(lambda n: card_counts.get(n, 0)) < 2]
    
    # Nightsoul point filtering 
    if "Natlan" not in characterdb.loc[characterdb['Name'].isin(decklist), 'Faction'].values:
        pool = pool[~pool['Effect'].str.contains("Nightsoul points", na=False)]
    
    # Elemental transfiguration filtering
    deck_elements = set(element_counts.keys())
    pool = pool[
        pool['TransfigElements'].isna() |
        pool['TransfigElements'].apply(lambda els: els is not None and deck_elements.issubset(set(els)))
    ]
    
    # eremite teatime/narizfasdfgtasdgf adventure multipart synergy card filtering
    pool = pool[
    (~pool['Name'].isin(MULTI_CONDITION_CARDS)) |
    (count_synergy_conditions() >= 2)
    ]
    
    # Silver and Melus functionality check 
    pool = pool[
    (pool['Name'] != "Silver and Melus") |
    three_unique_elements()
    ]

    # burning cards 
    pool = pool[
        (~pool['Name'].isin(BURNING_ARTIFACTS)) |
        ({"Pyro", "Dendro"}.issubset(element_counts.keys()))
    ]
    
    # guess
    pool = pool[
    (pool['Name'] != "Netochka") |
    netochka_condition_met()
    ]
    
    return pool

def select_card(name):
    global arcane_legend_selected, unique_weapons_in_deck, artifact_count_in_deck, card_counts, rating_history, tag_counts
    
    decklist.append(name)
    listbox.insert(tk.END, name)
    
    card_counts[name] = card_counts.get(name, 0) + 1
    
    row = card_pool.loc[card_pool['Name'] == name].iloc[0]
    
    if row['Group'] == "Arcane Legend":
        arcane_legend_selected = True
    if row['Name'].startswith("Elemental Transfiguration"):
        transfiguration_selected = True
    if group_starts_with(row['Group'],"Weapon "):
        unique_weapons_in_deck.add(row['Group'])
    if row['Group'] == "Artifact":
        artifact_count_in_deck += 1
    
    update_tag_counts(row, is_character=False)
    rating_history.append((row['Rank'], 1))
    
    valid_pool = get_valid_card_pool()
    rating_w = compute_rating_weights(valid_pool, rating_history, is_character=False)
    tag_w = compute_tag_weights(valid_pool)
    final_weights = rating_w * tag_w
    sampled = valid_pool.sample(n=min(3, len(valid_pool)), weights=final_weights)
    
    card_names = sampled['Name'].tolist()
    card_types = [f"{source}_Card" for source in sampled['SourcePool'].tolist()]
    
    display_options(card_names, card_types)
    
def fetch_fandom_card_image(card_name, card_type): #pulls card image based on name and type from wiki
    """Queries the Fandom API to get the true CDN URL, then fetches the image."""
    # 1. Format name to match Wiki naming conventions (spaces to underscores)
    formatted_name = card_name.replace(" ", "_")
    filename = f"File:{formatted_name}_{card_type}.png"

    # 2. Build the MediaWiki API request URL
    api_url = "https://genshin-impact.fandom.com/api.php"
    params = {
        "action": "query",
        "titles": filename,
        "prop": "imageinfo",
        "iiprop": "url",
        "format": "json",
    }
    headers = {"User-Agent": "GenshinDraftTool/0.01 (Contact: TheNecrosist@gmail.com)"}

    try:
        # Request the image metadata from the API
        api_response = requests.get(
            api_url, params=params, headers=headers, timeout=5
        )
        api_response.raise_for_status()
        data = api_response.json()

        # 3. Parse out the nested CDN URL from the JSON payload
        pages = data.get("query", {}).get("pages", {})
        page_id = list(pages.keys())[0]

        # Check if the page exists or if it returned an error (-1 means not found)
        if page_id == "-1":
            print(f"Card file '{filename}' could not be found on the wiki.")
            return None

        # Extract the direct raw asset link
        image_info = pages[page_id].get("imageinfo", [{}])[0]
        cdn_url = image_info.get("url")

        if not cdn_url:
            return None

        # 4. Fetch the raw image bytes from the static.wikia URL
        img_response = requests.get(cdn_url, headers=headers, timeout=5)
        img_response.raise_for_status()

        # Stream bytes into Pillow
        image_data = io.BytesIO(img_response.content)
        img = Image.open(image_data)

        # Optional: Resize the card to fit your UI layout
        img = img.resize((180, 300), Image.Resampling.LANCZOS)
        return img

    except Exception as e:
        print(f"Error programmatically fetching '{card_name}': {e}")
        return None

def get_card_image(name, card_type):
    """Checks disk cache first, falls back to wiki fetch, saves to disk if fetched fresh."""
    filename= re.sub(r'[<>:"/\\|?*]', '', name)
    path = os.path.join(CACHE_DIR, f"{filename}.png")
    
    if os.path.exists(path):
        return Image.open(path)
    
    raw_image = fetch_fandom_card_image(name, card_type)
    if raw_image:
        raw_image.save(path)
    return raw_image

def preload_images():
    """Runs once at startup - fills image_cache for every character in the db."""
    sources = [
        (characterdb, "Character_Card"),
        (equipment_db, "Equipment_Card"),
        (event_db, "Event_Card"),
        (support_db, "Support_Card"),
    ]
    
    total = sum(len(df) for df, _ in sources)
    count = 0
    
    loading_label = tk.Label(root, text="Loading images...", font=("Arial", 14), fg="white", bg="black")
    loading_label.grid(row=0, column=0, pady=20)
    
    for df, card_type in sources:
        for name in df['Name']:
            count += 1
            loading_label.config(text=f"Loading images... ({count}/{total}) — {name}")
            root.update()
            
            img = get_card_image(name, card_type)
            if img:
                image_cache[name] = ImageTk.PhotoImage(img)
    
    loading_label.grid_forget()

def get_card_description(name):
    """Looks up the Effect/description text for a card - characters are skipped (no tooltip)."""
    if card_pool is not None:
        row = card_pool.loc[card_pool['Name'] == name]
        if not row.empty:
            return row['Effect'].iloc[0]
    return ""  # empty string = ToolTip.show() will just do nothing (no text check passes)

def get_card_cost(name):
    """Looks up the Cost text for a card - characters skipped (no cost to show)."""
    if card_pool is not None:
        row = card_pool.loc[card_pool['Name'] == name]
        if not row.empty:
            return row['Formatted Cost'].iloc[0]
    return ""

def parse_cost(cost_str):
    """'3 Pyro, 2 Energy' -> [('3', 'Pyro'), ('2', 'Energy')]"""
    if not cost_str:
        return []
    parts = []
    for chunk in cost_str.split(","):
        chunk = chunk.strip()
        num, type_name = chunk.split(" ", 1)
        parts.append((num, type_name))
    return parts

def setup_grid():
    global card_canvases, name_labels, select_buttons, image_tooltips, cost_die_items, OVERHANG_Y, rating_canvases, tag_icon_canvases, rating_tooltips, tag_tooltips
    global theme_tracker_frame, theme_avg_canvas, theme_tag_widgets, theme_avg_tooltip
    
    card_canvases = []
    name_labels = []
    select_buttons = []
    image_tooltips = []
    cost_die_items = []
    rating_canvases = []
    rating_tooltips = []
    tag_icon_canvases = []
    tag_tooltips = []
    theme_tag_widgets = {}
    
    CARD_WIDTH = 180
    CARD_HEIGHT = 300
    OVERHANG_X = 16
    OVERHANG_Y = 8  # extra headroom so the -4 offset doesn't clip

    for i in range(3):
        canvas = tk.Canvas(root, width=CARD_WIDTH + OVERHANG_X, height=CARD_HEIGHT + OVERHANG_Y,
                            bg="black", highlightthickness=0)
        canvas.grid(row=0, column=i, padx=50, pady=(25, 5))
        card_canvases.append(canvas)
        image_tooltips.append(ToolTip(canvas))
        
        die_id_0 = canvas.create_image(0, OVERHANG_Y - 4, anchor="nw")
        die_id_1 = canvas.create_image(0, 0, anchor="nw")
        cost_die_items.append([die_id_0, die_id_1])
        
        name_label = tk.Label(root, bg="black", fg="white", font=("Arial", 14, "bold"),
                       wraplength=280, justify="center", anchor="center", height=3)
        name_label.grid(row=1, column=i, pady=5, sticky="ew")
        name_labels.append(name_label)
         
        info_frame = tk.Frame(root, bg="black", width=196, height=32)
        info_frame.grid(row=2, column=i, pady=(0, 5))
        info_frame.grid_propagate(False)
        
        rating_canvas = tk.Canvas(info_frame, width=32, height=32, bg="black", highlightthickness=0)
        rating_canvas.place(x=8, y=0)
        rating_canvases.append(rating_canvas)
        rating_tooltips.append(ToolTip(rating_canvas))
        
        tag_canvas = tk.Canvas(info_frame, width=140, height=40, bg="black", highlightthickness=0)
        tag_canvas.place(x=45, y=0)
        tag_icon_canvases.append(tag_canvas)
        tag_tooltips.append(ToolTip(tag_canvas))
        
        select_button = tk.Button(root, bg="black", fg="white", text="Select", font=("Arial", 12), width=20)
        select_button.grid(row=3, column=i, padx=5, pady=5)
        select_buttons.append(select_button)
        
    theme_tracker_frame = tk.Frame(root, bg="black")
    theme_tracker_frame.grid(row=4, column=0, columnspan=3, pady=(10, 5))
    theme_avg_canvas = tk.Canvas(theme_tracker_frame, width=80, height=64, bg="black", highlightthickness=0)
    theme_avg_canvas.pack(side="left", padx=(0, 15))
    theme_avg_tooltip = ToolTip(theme_avg_canvas)
    theme_avg_tooltip.set_text(RATING_SCALE_EXPLANATION)
        
def display_options(card_names, card_types):
    for i in range(3):
        name = card_names[i]
        canvas = card_canvases[i]
        
        canvas.delete("card_art")
        
        tk_image = image_cache.get(name)
        if tk_image:
            canvas.create_image(16, OVERHANG_Y, anchor="nw", image=tk_image, tags="card_art")
            canvas.card_art_ref = tk_image
            name_labels[i].config(text=name)
        else:
            name_labels[i].config(text=f"{name} (image unavailable)")
        
        select_buttons[i].config(command=lambda n=name: select(n), state="normal")
        canvas.tag_lower("card_art")
        
        image_tooltips[i].set_text(get_card_description(name))
        
        cost_parts = parse_cost(get_card_cost(name))
        if card_pool is not None:
            row = card_pool.loc[card_pool['Name'] == name]
            is_arcane_legend = not row.empty and row['Group'].iloc[0] == "Arcane Legend"
        else:
            is_arcane_legend = False

        for slot_idx in range(2):
            item_id = cost_die_items[i][slot_idx]
            
            if slot_idx == 1 and is_arcane_legend:
                composite = get_die_composite("ArcaneLegend", "")  # no number needed, just the badge
                canvas.itemconfig(item_id, image=composite, state="normal")
                canvas.coords(item_id, 0, OVERHANG_Y - 4 + dice_icon_images["ArcaneLegend"].size[1])
                if not hasattr(canvas, 'die_refs'):
                    canvas.die_refs = {}
                canvas.die_refs[slot_idx] = composite
            elif slot_idx < len(cost_parts):
                num, type_name = cost_parts[slot_idx]
                composite = get_die_composite(type_name, num)
                icon_height = dice_icon_images[type_name].size[1]
                y_pos = OVERHANG_Y - 4 if slot_idx == 0 else OVERHANG_Y - 4 + icon_height
                canvas.itemconfig(item_id, image=composite, state="normal")
                canvas.coords(item_id, 0, y_pos)
                if not hasattr(canvas, 'die_refs'):
                    canvas.die_refs = {}
                canvas.die_refs[slot_idx] = composite
            else:
                canvas.itemconfig(item_id, state="hidden")
            
        row = card_pool.loc[card_pool['Name'] == name] if card_pool is not None else None
        
        if card_pool is not None:
            row = card_pool.loc[card_pool['Name'] == name]
        else:
            row = characterdb.loc[characterdb['Name'] == name]

        if not row.empty:
            rating = int(row['Rank'].iloc[0])
            regular_tags = row['TagList'].iloc[0]
            dependent_tags = row['DependentTagList'].iloc[0]
        else:
            rating = None
            regular_tags, dependent_tags = [], []

        rating_canvas = rating_canvases[i]
        rating_canvas.delete("all")
        if rating is not None:
            if rating_bg_image:
                rating_canvas.create_image(0, 0, anchor="nw", image=rating_bg_image)
            text_img = get_rating_text_image(rating)
            rating_canvas.create_image(0, 0, anchor="nw", image=text_img)
        rating_tooltips[i].set_text(RATING_SCALE_EXPLANATION)
        
        tag_canvas = tag_icon_canvases[i]
        tag_canvas.delete("all")
        tag_canvas.tag_refs = []
        
        positions = [(0, 0), (36, 0), (72, 0), (108, 0)]  # single row, spread across the wider canvas
        all_tags = [(t, False) for t in regular_tags] + [(t, True) for t in dependent_tags]
        
        for idx, (tag, is_dep) in enumerate(all_tags[:4]):
            icon_dict = tag_icon_images_dep if is_dep else tag_icon_images
            icon = icon_dict.get(tag)
            if icon:
                photo = ImageTk.PhotoImage(icon.resize((32, 32)))
                tag_canvas.create_image(*positions[idx], anchor="nw", image=photo)
                tag_canvas.tag_refs.append(photo)
        
        tag_tooltips[i].set_text(build_tag_tooltip_text(regular_tags, dependent_tags))

def select_character(card_name): #adds selected card to list 
    global banned_elements, character_pool, element_counts, faction_counts, rating_history, tag_counts
    decklist.append(card_name)
    listbox.insert(tk.END, card_name)
    
    element = characterdb.loc[characterdb['Name'] == card_name, 'Element'].iloc[0]
    faction = characterdb.loc[characterdb['Name'] == card_name, 'Faction'].iloc[0]
    faction_counts[faction] = faction_counts.get(faction, 0) + 1
    element_counts[element] = element_counts.get(element, 0) + 1
    
    banned_elements |= ELEMENT_CONFLICTS[element]
    if element_counts[element] >= 2:
        banned_elements.add(element)  # no 3rd of this element allowed
    
    char_row = characterdb.loc[characterdb['Name'] == card_name].iloc[0]
    rating_history.append((char_row['Rank'], 10))
    update_tag_counts(char_row, is_character=True)
    
    valid_pool = character_pool[~character_pool['Element'].isin(banned_elements)]
    rating_w = compute_rating_weights(valid_pool, rating_history, is_character=True)
    tag_w = compute_tag_weights(valid_pool)
    final_weights = rating_w * tag_w
    
    display_options(valid_pool.sample(n=min(3, len(valid_pool)), weights=final_weights)['Name'].tolist(), "Character_Card")
    
    character_pool = character_pool[character_pool['Name'] != card_name]
    valid_pool = character_pool[~character_pool['Element'].isin(banned_elements)]
    
    display_options(valid_pool.sample(n=3)['Name'].tolist(), "Character_Card")

def select(name):
    """Single entry point for both phases - routes to the right handler."""
    global DRAFT_PHASE
    
    if DRAFT_PHASE == "character":
        select_character(name)
        
        if len(decklist) == 3:
            DRAFT_PHASE = "cards"
            start_card_draft()
    else:
        select_card(name)
        if len(decklist) == 33:
            finalize_draft()
            
    update_theme_tracker()
    
def start_card_draft():
    """Called once, right when character drafting ends - builds the pool and shows the first 3 cards."""
    global card_pool
    card_pool = build_card_pool()
    
    valid_pool = get_valid_card_pool()
    rating_w = compute_rating_weights(valid_pool, rating_history, is_character=False)
    tag_w = compute_tag_weights(valid_pool)
    final_weights = rating_w * tag_w
    sampled = valid_pool.sample(n=min(3, len(valid_pool)), weights=final_weights)
    
    card_names = sampled['Name'].tolist()
    card_types = [f"{source}_Card" for source in sampled['SourcePool'].tolist()]
    
    display_options(card_names, card_types)

def generate_deck_code(decklist):
    share_ids = []
    missing_cards = []
    filler_swaps = []  # (original_name, filler_name) pairs
    filler_index = 0
    
    for idx, name in enumerate(decklist):
        is_character = idx < 3
        share_id = get_share_id(name)
        
        if share_id is not None:
            share_ids.append(str(share_id))
            continue
        
        missing_cards.append(name)
        
        if is_character and filler_index < len(FILLER_CHARACTERS):
            filler_name = FILLER_CHARACTERS[filler_index]
            filler_index += 1
            filler_id = get_share_id(filler_name)
            if filler_id is not None:
                share_ids.append(str(filler_id))
                filler_swaps.append((name, filler_name))
    
    ids_str = ",".join(share_ids)
    url = f"https://genshin-db-api.vercel.app/api/tcgdeckshare/encode?deck={ids_str}"
    response = requests.get(url)
    response.raise_for_status()
    return response.json()["deckcode"], missing_cards, filler_swaps
    
def show_deck_code_window(deck_code, missing_cards, filler_swaps):
    code_window = tk.Toplevel(root)
    code_window.title("Your Deck Code")
    code_window.configure(bg="black")
    code_window.transient(root)
    code_window.iconbitmap("caticon.ico")
    
    def bring_to_front(event=None):
        try:
            code_window.lift()
        except tk.TclError:
            pass
    map_binding = root.bind("<Map>", bring_to_front)
    
    label = tk.Label(code_window, text="Draft complete! Your deck code:", 
                      font=("Arial", 14), fg="white", bg="black")
    label.pack(pady=10, padx=20)
    
    code_entry = tk.Entry(code_window, font=("Consolas", 12), width=50, justify="center",
                           bg="black", fg="white", readonlybackground="black", insertbackground="white")
    code_entry.insert(0, deck_code)
    code_entry.configure(state="readonly")
    code_entry.pack(pady=10, padx=20)
    
    def cleanup_and_close():
        root.unbind("<Map>", map_binding)
        code_window.destroy()
    
    code_window.protocol("WM_DELETE_WINDOW", cleanup_and_close)  # also handles clicking the window's X button
    
    def copy_to_clipboard():
        code_window.clipboard_clear()
        code_window.clipboard_append(deck_code)
        copy_button.config(text="Copied!")
        code_window.after(1500, lambda: copy_button.config(text="Copy to Clipboard"))
    
    copy_button = tk.Button(code_window, text="Copy to Clipboard", command=copy_to_clipboard, font=("Arial", 12), fg="white", bg="black")
    copy_button.pack(pady=10)
    
    if missing_cards:
        warning_label = tk.Label(code_window, text="⚠ Missing share IDs - add these manually:",
                                  font=("Arial", 11, "bold"), fg="orange", bg="black")
        warning_label.pack(pady=(15, 5))
        
        missing_list = tk.Label(code_window, text="\n".join(missing_cards),
                                 font=("Arial", 10), fg="white", bg="black", justify="center")
        missing_list.pack(pady=(0, 10))
    
    if filler_swaps:
        swap_label = tk.Label(code_window, text="Character(s) replaced with filler for import:",
                               font=("Arial", 11, "bold"), fg="orange", bg="black")
        swap_label.pack(pady=(10, 5))
        
        swap_text = "\n".join(f"{original} → {filler}" for original, filler in filler_swaps)
        swap_list = tk.Label(code_window, text=swap_text,
                              font=("Arial", 10), fg="white", bg="black", justify="center")
        swap_list.pack(pady=(0, 10))
    
    def start_new_draft():
        cleanup_and_close()
        reset_draft()
    
    new_draft_button = tk.Button(code_window, text="New Draft", command=start_new_draft, font=("Arial", 12), fg="white", bg="black")
    new_draft_button.pack(pady=10)

def lock_draft_ui():
    """Disables all selection buttons so nothing can be added after the deck is finalized."""
    for btn in select_buttons:
        btn.config(state="disabled")
    
def finalize_draft():
    status_label = tk.Label(root, text="Generating deck code...", font=("Arial", 14), fg="white", bg="black")
    status_label.grid(row=0, column=0, columnspan=3, pady=20)
    root.update()
    
    lock_draft_ui()
    
    try:
        deck_code, missing_cards, filler_swaps = generate_deck_code(decklist)
    except Exception as e:
        status_label.config(text=f"Failed to generate deck code: {e}")
        return
    
    status_label.grid_forget()
    show_deck_code_window(deck_code, missing_cards, filler_swaps)
    
def reset_draft():
    """Resets all draft state and starts a brand new draft from scratch."""
    global DRAFT_PHASE, decklist, character_pool, card_pool
    global banned_elements, element_counts, faction_counts
    global arcane_legend_selected, unique_weapons_in_deck, artifact_count_in_deck, card_counts, transfiguration_selected, rating_history, tag_counts
    global theme_avg_canvas, theme_tag_widgets
    
    DRAFT_PHASE = "character"
    decklist = []
    character_pool = characterdb.copy()
    card_pool = None
    
    banned_elements = set()
    element_counts = {}
    faction_counts = {}
    listbox.delete(0, tk.END)  
    
    arcane_legend_selected = False
    unique_weapons_in_deck = set()
    artifact_count_in_deck = 0
    card_counts = {}
    
    tag_counts = {}       # theme -> weighted count so far
    rating_history = []  # ratings of picked including characters
    
    theme_avg_canvas.delete("all")
    for tag, (wrapper, _, _) in theme_tag_widgets.items():
        wrapper.destroy()
    theme_tag_widgets.clear()
    
    update_theme_tracker()
    
    for btn in select_buttons:
        btn.config(state="normal")
    
    initial_chars = character_pool.sample(n=3)['Name'].tolist()
    display_options(initial_chars, ["Character_Card"] * 3)

  
root = tk.Tk()
root.configure(bg="black")
root.title("Genshin TCG Draft Tool")
root.iconbitmap("caticon.ico")

CACHE_DIR = "image_cache"
os.makedirs(CACHE_DIR, exist_ok=True)
image_cache = {}  # name -> PhotoImage, held in memory for instant Tkinter access

if __name__ == "__main__": # calls everything for startup within an exception handler so it writes log for errors
    try:
        preload_images()
        load_dice_icons()
        load_tag_icons()
        load_rating_bg()
        
        with open('action_shareids.json') as f:
            action_shareids = json.load(f)
        with open('character_shareids.json') as f:
            character_shareids = json.load(f)
        with open('manual_shareid_overrides.json') as f:
            manual_overrides = json.load(f)
        
        listbox = tk.Listbox(root, bg="black", fg="white", width=50, height=33)
        listbox.grid(row=0, rowspan=34, column=4, padx=5, pady=10)

        
        setup_grid()
        reset_draft()

        random_chars = characterdb.sample(n=3) # first pick, just any 3 characters randomly pulled 
        characterNames = random_chars['Name'].tolist()
        display_options(characterNames,"Character_Card")
        
        root.mainloop()
        
    except Exception:
        log_exception_to_file(*sys.exc_info())



