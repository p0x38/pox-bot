import datetime
import subprocess
import json
import os
import random
import sqlite3
import time
import unicodedata
import logging
import re
import base64
import aiofiles
import dotenv
from typing import Optional

dotenv.load_dotenv()

from discord import Interaction

import data

if not os.path.exists('./logs'):
    os.makedirs('./logs',exist_ok=True)

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

def is_bot_owner(interaction: Interaction) -> bool:
    return interaction.user.id == 457436960655409153

def get_bot_token():
    logger.debug("Retrieving token...")
    return os.getenv('TOKEN')

def get_lmstudio_token():
    return os.getenv("LM_API_TOKEN")

def get_openai_api_key():
    return os.getenv("OPENAI_API_KEY")

def get_mysql_credentials():
    logger.debug("Retrieving MySQL credentials...")
    user = os.getenv('MYSQL_USER')
    password = os.getenv('MYSQL_PASS')
    return user, password

def get_pid():
    return os.getpid()

def _find_key_recursive(config: dict,key) -> bool:
    if key in config:
        logging.debug(f"Found key '{key}' at a nested level.")
        return True
    
    for value in config.values():
        if isinstance(value, dict):
            if _find_key_recursive(value,key):
                return True
    
    return False

def set_if_not_exists(config: dict, key, value):
    try:
        for k,v in config.items():
            logger.debug(f"ArrayKey: {k}")
            if k == key:
                return
        config[key] = value
    except Exception as e:
        logger.error(f"Exception occured; {e} 3:")
        return False
    return True

def cset(config: dict, key, value):
    try: config[key] = value
    except Exception as e:
        logger.error(f"Exception occured while trying to set config {key} to {value}: {e} 3:") 
        return False
    return True

async def isInt(s):
    try:
        logger.debug(f"Checking if {s} is integer")
        int(s,10)
    except ValueError:
        logger.debug(f"{s} is not integer")
        return False
    else:
        logger.debug(f"{s} is integer")
        return True

async def change_toggles(config,key):
    if not key or not config:
        logger.error(f"{key} not found! 3:")
        return
    config[key] = not config[key]
    logger.info(f"Set {key} to {config[key]}! :3")
    print("Found")
    return

def muffle(text: str):
    result = []
    for char in text:
        logger.debug(f"Target: {char}")
        target = char
        if target.isalpha():
            logger.debug(f"The char is alphabet")
            if target not in 'whpmnuf':
                logger.debug(f"The char {char} will be replaced with 'm'")
                target = "m"
        
        logger.debug(f"Appending text {char}")
        result.append(target)

    logger.debug(f"Process completed!\nResult: {"".join(result)} ({text})")
    return "".join(result) + f" ({text})"

def uwuify(uwu,text: str):
    logger.debug(f"Processing {text} with Uwuifier")
    return uwu.uwuify(text)

def save(config: dict):
    logger.debug(f"Saving data to settings.json")
    with open("settings.json","w",encoding="utf-8") as f:
        json.dump(config,f,ensure_ascii=False,indent=4)

def create_dir_if_not_exists(path):
    if not os.path.exists(path):
        logger.debug(f"Folder {path} not found. creating directory...")
        os.makedirs(path,exist_ok=True)

def format_extra(input:str):
    logger.debug(f"Input: {input}")
    if not input:
        logger.debug(f"Input shouldn't be empty")
        return ""
    
    result = ""
    i = 0
    while i < len(input):
        logger.debug(f"Index: {i}, {input[i]}")
        char = input[i]
        if char == '+':
            logger.debug("Char is '+'")
            if i > 0:
                plus = 0
                j = i
                while j < len(input) and input[j] == '+':
                    plus += 1
                    j += 1
                
                rep = input[i-1]
                repeats = random.randint(1,plus)
                result += rep*repeats
                i=j
            else:
                i += 1
        else:
            result += char
            i += 1
    return result

def setup_database(database):
    logger.debug("Setting database...")
    conn = sqlite3.connect(database)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS leaderboard (
            user_id TEXT PRIMARY KEY,
            pox_count INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS words (
            user_id TEXT PRIMARY KEY,
            amount INTEGER
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS custom (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            query TEXT UNIQUE,
            author_id INT,
            timestamp REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS xp (
            user_id TEXT INTEGER PRIMARY KEY,
            xp INTEGER,
            level INTEGER,
            last_xp_gain REAL
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS counts (
            id INTEGER PRIMARY KEY,
            total INTEGER
        )
    """)
    # cursor.execute("""
    #     CREATE TABLE IF NOT EXISTS messages (
    #         id INTEGER PRIMARY KEY,
    #         content TEXT,
    #         user_id INTEGER,
    #         timestamp REAL,
    #         channel INTEGER
    #     )
    # """)
    conn.commit()
    conn.close()

def three_commas(x):
    b,a = divmod(len(x), 3)
    return ",".join(([x[:a]] if a else []) + [x[a+3*i:a+3*i+3] for i in range(b)])

def is_weekday(time: datetime.datetime):
    weekday = time.weekday()

    if weekday >= 0 and weekday <= 4:
        return True
    else:
        return False

def is_specificweek(time: datetime.datetime,week:int):
    weekday = time.weekday()

    if weekday == week:
        return True
    else:
        return False

def is_within_hour(time: datetime.datetime,fromhour:int,tohour:int):
    hour = time.hour

    if hour >= fromhour and hour < tohour:
        return True
    else:
        return False

def is_sleeping(time: datetime.datetime,fromhour:int,tohour:int):
    hour = time.hour

    if hour >= fromhour or hour < tohour:
        return True
    else:
        return False

"""
def check_map(score: float,max:int):
    map = data.possible_map
    map_len = len(map)
    size = max // map_len

    scores = {}
    for i, name in enumerate(map):
        start = i * size
        end = start + size
        if i == map_len-1:
            end = max+1
        scores[range(start,end)] = name
    for sr,txt in scores.items():
        if score in sr:
            return map[txt]
"""

def check_map():
    return random.choice(data.possibility_words)

def get_formatted_from_seconds(seconds):
    days, remainder = divmod(seconds, 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)

    if days > 0:
        return f"{int(days):02d} d, {int(hours):02d}h, {int(minutes):02d}m, and {int(seconds):02d}s"
    return f"{int(hours):02d}h, {int(minutes):02d}m, and {int(seconds):02d}s"

def get_case_pattern(word):
    return [char.isupper() for char in word]

def apply_case_pattern(word, pattern):
    new_word = ""
    for i, char in enumerate(word):
        if i < len(pattern) and pattern[i]:
            new_word += char.upper()
        else:
            new_word += char.lower()
    return new_word

def meow_clean_phrase(phrase):
    return ''.join(char for char in phrase if char.isalpha() or char.isspace())

def to_meow_weighted(word):
    numberd = [0,1,2]
    weightgg = [50,2,1]
    ran = random.choices(numberd,weights=weightgg)[0]
    meows = ["meow","miaw","maow"]
    first_char = word[0] if word else None
    length = len(word)
    if not length:
        return ""
    
    case_pattern = get_case_pattern(word)
    
    if length == 3:
        return apply_case_pattern("maw",case_pattern)
    elif length < 4:
        return apply_case_pattern(meows[ran],case_pattern)
    
    """
    if length < 4:
        if word.isupper():
            return "MEOW"
        elif word.islittle():
            return "Meow"
        else:
            return "meow"
    """
    
    weights = {
        'm':3,
        'e':3,
        'i':3,
        'o':3,
        'a':3,
        'w':3
    }
    total_weight = sum(weights.values())
    
    match ran:
        case 0:
            mc = round(length * (weights['m'] / total_weight))
            ec = round(length * (weights['e'] / total_weight))
            oc = round(length * (weights['o'] / total_weight))
            wc = round(length * (weights['w'] / total_weight))
        case 1:
            mc = round(length * (weights['m'] / total_weight))
            ec = round(length * (weights['i'] / total_weight))
            oc = round(length * (weights['a'] / total_weight))
            wc = round(length * (weights['w'] / total_weight))
        case 2:
            mc = round(length * (weights['m'] / total_weight))
            ec = round(length * (weights['a'] / total_weight))
            oc = round(length * (weights['o'] / total_weight))
            wc = round(length * (weights['w'] / total_weight))
        case _:
            mc = round(length * (weights['m'] / total_weight))
            ec = round(length * (weights['e'] / total_weight))
            oc = round(length * (weights['o'] / total_weight))
            wc = round(length * (weights['w'] / total_weight))
    
    current_length = mc + ec + oc + wc
    diff = length - current_length
    
    if diff > 0:
        oc += diff//2
        ec += diff - (diff//2)
    elif diff < 0:
        oc -= abs(diff//2)
        ec -= abs(diff) - abs(diff//2)
    
    match ran:
        case 0:
            meow_word = ("m"*mc)+("e"*ec)+("o"*oc)+("w"*wc)
        case 1:
            meow_word = ("m"*mc)+("i"*ec)+("a"*oc)+("w"*wc)
        case 2:
            meow_word = ("m"*mc)+("a"*ec)+("o"*oc)+("w"*wc)
        case _:
            meow_word = ("m"*mc)+("e"*ec)+("o"*oc)+("w"*wc)
    
    return apply_case_pattern(meow_word, case_pattern)

def meow_phrase_weighted(phrase):
    final_phrase = ""
    current_word = ""
    
    for char in phrase:
        if char.isalpha():
            current_word += char
        else:
            if current_word:
                final_phrase += to_meow_weighted(current_word)
                current_word = ""
            final_phrase += char
    
    if current_word:
        final_phrase += to_meow_weighted(current_word)
    
    return final_phrase

def to_uwu(text: str) -> str:
    regex_maps = [
        (r'hey','hay'),
        (r'dead','ded'),
        (r'n[aeiou]*t', 'nd'),
        (r'read','wead'),
        (r'that','dat'),
        (r'th(?!e)','f'),
        (r've','we'),
        (r'le$','wal'),
        (r'ry','wwy'),
        (r'[rw]','w'),
        (r'll','w'),
        (r'[aeiur]l$','wl'),
        (r'ol','owl'),
        (r'[lr]o','wo'),
        (r'([bcdfghjkmnpqstxyz])o','\\1wo'),
        (r'[vw]le','wal'),
        (r'fi','fwi'),
        (r'ver','wer'),
        (r'poi','pwoi'),
        (r'(?:dfghjpqrstxyz)le$','\\1wal'),
        (r'ly','wy'),
        (r'ple','pwe'),
        (r'nr','nw'),
        (r'mem','mwem'),
        (r'nywo','nyo'),
        (r'fuc','fwuc'),
        (r'mom','mwom'),
        (r'^me$', 'mwe'),
        (r'n(?:[aeiou])','ny\\1'),
        (r'ove','uv'),
        (r'\b(?:ha|hah|heh|hehe)+\b','hehe'),
        (r'the','teh'),
        (r'\byou\b','u'),
        (r'\btime\b','tim'),
        (r'over','ower'),
        (r'worse','wose'),
        (r'great','gwate'),
        (r'aviat','awiat'),
        (r'dedicat','deditat'),
        (r'remember','rember'),
        (r'when','wen'),
        (r'frighten(ed)*','\\1rigten'),
        (r'meme','mem'),
        (r'feel$','fell'),
        (r'(?:[<>])?[:;=\'_]+-?[\)\]\>]+',"\\1:3"),
        (r'[<\[\(]+-?[:;=\'_]+(?:[<>])?',"\\1:3"),
        (r'(?:[>])?[:;=\'_]+-?[\(\[\<]+',"3:\\1"),
        (r'[>?\]\)]+-?[:;=\'_]+(?:[<>])?',"3:\\1"),
        (r'(?:[><])?[xX:;=\']+[dD]+',"\\1x3"),
        (r'[dD]+[xX:;=\']+(?:[><])?',"\\1x3"),
    ]
    try:
        text = text.lower()
        
        words = text.split(" ")
        
        for index, word in enumerate(words):
            logger.debug(f"Index: {index}, {word}")
            if not word:
                logger.debug("The word is empty! skipping...")
                continue
            
            if word[0] in ("@","#",":","<","$","!","&","/"):
                logger.debug("The word including special characters! skipping...")
                continue
            
            stutter = ""
            for regex, replace_to in regex_maps:
                if re.match(regex,word):
                    logger.debug(f"Resolving {regex} as {replace_to} with {word}")
                    word = re.sub(regex,replace_to,word)
            
            if unicodedata.category(word[0]).lower().startswith("l"):
                if random.random() > 0.121:
                    stutter += "".join([f"{word[0]}-" for _ in range(random.randint(1,3))])
                word = stutter + word[0] + word[1:]
            
            words[index] = word
        
        return " ".join(words)
    except Exception as e:
        print(e)
        return text

def base64_encode(text: str):
    return base64.b64encode(text.encode()).decode()

def base64_decode(b64: str):
    return base64.b64decode(b64.encode()).decode()

def generate_namesignature():
    string = ""
    for i in range(random.randint(3,5)):
        string += random.choice(list(data.alphabet_masks))[0]
    
    if random.randint(0,20) == 0:
        for i in range(random.randint(2,3)):
            string += str(random.randint(0,9))
    
    return string.upper()

def get_latest_commit_message():
    try:
        result = subprocess.run(
            ['git','log','-1','--pretty=%B'],
            cwd='.',
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        logger.error(f"Error occured: {e}")
        return None
    except FileNotFoundError:
        logger.error("git command not found")
        return None

def approach_target(target: float,max_iterations: int = 125, x: float = 1.75,current_range:tuple = (-5,5),step_varience: tuple = (.5,2)):
    cmin,cmax = current_range
    current = random.uniform(target+cmin,target+cmax)
    history = [current]
    iterations = 0
    
    while abs((target - current)) > 0.25 or iterations < max_iterations:
        diff = target - current
        smin,smax = step_varience
        step = diff*random.uniform(smin,smax)*x
        current+= step
        
        history.append(current)
        iterations += 1
    
    return history

def clamp(n:int,min:int,max:int):
    if n < min: return min
    elif n > max: return max
    else: return n
def clamp_f(n:float,min:float,max:float):
    if n < min: return min
    elif n > max: return max
    else: return n

async def get_markov_dataset(name: str = "2"):
    if not os.path.exists(f"./resources/{name}.txt"):
        logger.error("The file not found")
        return None
    async with aiofiles.open(f"./resources/{name}.txt", 'r', encoding="utf-8") as f:
        line = await f.read()
    
    lines = line.split("\n")
    
    return lines

def get_latency_from_uhhh_time(interval: float = 1, iterations: int = 2):
    results = []
    
    last = None
    
    for i in range(iterations):
        current = datetime.datetime.now()
        
        if last:
            delay = (current - last)
            results.append(delay.microseconds)
        
        last = current
        time.sleep(interval/1000)
    
    return results

def check_string_for_hex(s):
    hexs = set('0123456789abcdef#')
    return all(char.lower() not in hexs for char in s)

def expand_hex_old(s):
    if check_string_for_hex(s):
        if len(s) == 4 and s.startswith('#'):
            return ''.join(c*2 for c in s[1:])
        elif len(s) == 3:
            return ''.join(c*2 for c in s)
        elif len(s) == 9 and s.startswith('#'):
            return s[1:]
        elif len(s) == 8:
            return s
        else:
            return None

def truncate(text,length=4000):
    return (text[:length-1]+'…') if len(text) > length else text

def expand_hex(short: str) -> str:
    clean_hex = short.lstrip('#').lower()

    if len(clean_hex) != 3:
        return "000000"
    
    if not re.fullmatch(r'[0-9a-f]{3}', clean_hex):
        return "000000"
    
    r,g,b = clean_hex[0], clean_hex[1], clean_hex[2]

    expanded = f"{r}{r}{g}{g}{b}{b}"

    return expanded

def crop_word(text, needle_word, padding=8, emphasis=True):
    start = text.lower().find(needle_word.lower())
    if start == -1: return None

    if emphasis:
        # emphasis the needle word in text
        needle_len = len(needle_word)
        text = (text[:start] + "**" + text[start:start+needle_len] + "**" + text[start+needle_len:])
        start += 2  # account for added asterisks

    low = max(0, start - padding)
    high = min(len(text), start + len(needle_word) + padding)

    return text[low:high]

def get_int(i):
    try:
        return int(i)
    except ValueError:
        return 0
    except Exception:
        return -1

def format_boolean(i: Optional[bool], true_text: str = "Yes", false_text: str = "No"):
    if not i: return "None"
    return true_text if i == True else false_text

def format_seconds(i: Optional[int]):
    if not i: return "???"
    suffix = "seconds" if i > 1 else "second"
    return f"{i} {suffix}"
