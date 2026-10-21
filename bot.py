import datetime as dt
import os
import random
import re

import aiohttp
import discord
from dotenv import load_dotenv

load_dotenv()
TOKEN = os.getenv("DISCORD_TOKEN")

REAL_FORECAST_CHANCE = 0.10
RANDOM_IDK_CHANCE = 0.08
EXTRA_COMMENTARY_CHANCE = 0.30
ONE_WORD_CHANCE = 0.15
SKY_LEAD_CHANCE = 0.20
PREFIX_CHANCE = 0.12
SUFFIX_CHANCE = 0.15

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)

STOP_WORDS = {
    "what", "whats", "what's", "will", "the", "weather", "be", "going", "to",
    "like", "is", "it", "gonna", "forecast", "tomorrow", "today", "tonight",
    "in", "for", "at", "how", "hows", "how's", "does", "do", "are", "there",
    "a", "of", "day", "after", "outside", "up", "with", "gon", "tmrw", "tmr",
    "rain", "snow", "raining", "snowing", "hot", "cold", "warm", "sunny",
    "storm", "stormy", "get", "gets", "have", "has", "can", "you", "tell",
    "me", "please", "pls", "hey", "hi", "weathergirl", "its", "it's", "next",
    "this", "now", "right", "on", "would", "should", "could", "wanna", "want",
    "know", "check", "see", "lookup", "look", "about",
}
DIRECTION_WORDS = {"north", "south", "east", "west", "northern", "southern",
                   "eastern", "western", "central", "downtown"}

MONTHS = {
    "january": 1, "jan": 1, "february": 2, "feb": 2, "march": 3, "mar": 3,
    "april": 4, "apr": 4, "may": 5, "june": 6, "jun": 6, "july": 7, "jul": 7,
    "august": 8, "aug": 8, "september": 9, "sept": 9, "sep": 9,
    "october": 10, "oct": 10, "november": 11, "nov": 11,
    "december": 12, "dec": 12,
}
MONTH_RE = "|".join(sorted(MONTHS, key=len, reverse=True))
WEEKDAYS = ["monday", "tuesday", "wednesday", "thursday", "friday",
            "saturday", "sunday"]

DATE_MD = re.compile(
    rf"\b({MONTH_RE})\.?\s+(\d{{1,2}})(?:st|nd|rd|th)?\b(?:,?\s+(\d{{4}}))?")
DATE_DM = re.compile(
    rf"\b(\d{{1,2}})(?:st|nd|rd|th)?\s+(?:of\s+)?({MONTH_RE})\b(?:,?\s+(\d{{4}}))?")
DATE_NUM = re.compile(r"\b(\d{1,2})/(\d{1,2})(?:/(\d{2,4}))?\b")
WEEKDAY_RE = re.compile(r"\b(?:(?:next|this)\s+)?(" + "|".join(WEEKDAYS) + r")\b")


def extract_location(text: str) -> str:
    text = text.lower().replace("?", " ").replace("!", " ").replace(",", " ")
    padded = f" {text} "
    if " in " in padded:
        text = padded.rsplit(" in ", 1)[-1]
    words = [w for w in re.split(r"\s+", text) if w and w not in STOP_WORDS]
    return " ".join(words).strip()


def parse_when(text: str):
    t = text.lower()

    m = DATE_MD.search(t)
    if m:
        mon, day, yr = MONTHS[m.group(1)], int(m.group(2)), m.group(3)
    else:
        m = DATE_DM.search(t)
        if m:
            day, mon, yr = int(m.group(1)), MONTHS[m.group(2)], m.group(3)
        else:
            m = DATE_NUM.search(t)
            if m:
                first, second, yr = int(m.group(1)), int(m.group(2)), m.group(3)
                padded = m.group(1).startswith("0")
                if second <= 12 and (first > 12 or padded):
                    day, mon = first, second
                else:
                    mon, day = first, second
    if m:
        year = int(yr) if yr else None
        if year is not None and year < 100:
            year += 2000
        cleaned = t[:m.start()] + " " + t[m.end():]
        return {"kind": "date", "month": mon, "day": day, "year": year}, cleaned

    m = WEEKDAY_RE.search(t)
    if m:
        cleaned = t[:m.start()] + " " + t[m.end():]
        return {"kind": "weekday", "wd": WEEKDAYS.index(m.group(1))}, cleaned

    if "day after tomorrow" in t:
        return {"kind": "offset", "n": 2, "label": "the day after tomorrow"}, t
    if "tonight" in t or "today" in t or "right now" in t:
        return {"kind": "offset", "n": 0, "label": "today"}, t
    return {"kind": "offset", "n": 1, "label": "tomorrow"}, t


def resolve_when(when: dict, dates: list):
    today = dates[0]

    if when["kind"] == "offset":
        return "ok", when["n"], when["label"]

    if when["kind"] == "weekday":
        ahead = ((when["wd"] - today.weekday()) % 7) or 7
        return "ok", ahead, f"on {WEEKDAYS[when['wd']].capitalize()}"

    year = when["year"] or today.year
    try:
        target = dt.date(year, when["month"], when["day"])
    except ValueError:
        return "invalid", None, None

    if when["year"] is None and target < today and (today - target).days > 30:
        try:
            target = dt.date(year + 1, when["month"], when["day"])
        except ValueError:
            return "invalid", None, None

    if target < today:
        return "past", None, None
    if target not in dates:
        return "far", None, None

    label = f"on {target.strftime('%B')} {target.day}"
    return "ok", dates.index(target), label


async def geocode(session: aiohttp.ClientSession, name: str):
    url = "https://geocoding-api.open-meteo.com/v1/search"
    async with session.get(url, params={"name": name, "count": 1}) as r:
        data = await r.json()
    results = data.get("results")
    if not results:
        return None
    return results[0]


async def find_place(session, name: str):
    place = await geocode(session, name)
    if place:
        return place
    trimmed = " ".join(w for w in name.split() if w not in DIRECTION_WORDS)
    if trimmed and trimmed != name:
        return await geocode(session, trimmed)
    return None


async def get_forecast(session, lat, lon):
    url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "daily": "temperature_2m_max,temperature_2m_min,"
                 "precipitation_probability_max,weather_code,wind_speed_10m_max",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "timezone": "auto",
        "forecast_days": 16,
    }
    async with session.get(url, params=params) as r:
        data = await r.json()
    d = data["daily"]
    return {
        "dates": [dt.date.fromisoformat(x) for x in d["time"]],
        "days": [
            {
                "high": d["temperature_2m_max"][i],
                "low": d["temperature_2m_min"][i],
                "rain_chance": d["precipitation_probability_max"][i] or 0,
                "code": d["weather_code"][i],
                "wind": d["wind_speed_10m_max"][i] or 0,
            }
            for i in range(len(d["time"]))
        ],
    }


def sky_type(code: int) -> str:
    if code in (0, 1):
        return "clear"
    if code in (2, 3):
        return "cloudy"
    if code in (45, 48):
        return "fog"
    if code in (51, 53, 55, 56, 57, 61, 63, 65, 66, 67, 80, 81, 82):
        return "rain"
    if code in (71, 73, 75, 77, 85, 86):
        return "snow"
    if code in (95, 96, 99):
        return "storm"
    return "clear"


TEMP_LINES = [
    (20, [
        "uhhh... like. really cold. dont go outside",
        "its gonna be freezing bro. like actually freezing",
        "cold. so cold. idk the number but its cold",
        "your face is gonna hurt if you go outside",
        "its so cold i cant even think of a joke",
        "like. polar bear weather",
        "its gonna be cold {when}. like dangerously cold probably",
        "put on every jacket you own. all of them",
        "its basically the inside of a freezer out there",
        "if you go outside you are choosing violence against yourself",
        "its cold enough that spit might freeze idk. dont lick a popsicle",
        "stay inside",
        "your eyelashes are gonna freeze together probably",
    ], ["freezing", "arctic", "death"]),
    (40, [
        "uhhh... cold probably. idk",
        "its gonna be cold {when}. bring a jacket or whatever",
        "cold-ish? yeah cold",
        "jacket weather. maybe two jackets",
        "its giving cold",
        "bro i would not wear shorts",
        "cold. but like. survivable",
        "hat and gloves kinda day",
        "your nose is gonna be cold i think",
        "its cold. thats all i got",
        "cold. like. cold cold",
        "its gonna be cold enough to see your breath maybe",
        "wear a coat. i believe in you",
        "cold. my toes hurt just thinking about it",
    ], ["cold", "brrr"]),
    (55, [
        "kinda chilly i think",
        "like. sweater weather i guess",
        "its gonna be a little cold but not like. cold cold",
        "hoodie weather",
        "not cold enough to complain not warm enough to be happy",
        "its chilly {when}. bring a hoodie",
        "cozy weather i think. cozy",
        "fall vibes. even if its not fall",
        "a lil nippy",
        "kinda cool out. like a cool cool. not a cold cold",
        "long sleeves. thats my advice",
        "its that weather where you bring a jacket and then carry it",
    ], ["chilly", "cool"]),
    (70, [
        "its gonna be nice i think? like not hot not cold",
        "mild. thats the word...",
        "its fine. its just fine out",
        "perfect weather honestly. go touch grass please",
        "goldilocks weather? maybe?",
        "its giving weather",
        "very normal",
        "you wont even notice the weather its that mild",
        "jacket optional",
        "its gonna be {when} what you would call pleasant",
        "honestly kind of perfect. dont tell anyone",
    ], ["mild", "nice", "fine", "normal", "pleasant", "it's okay"]),
    (80, [
        "its gonna be warm {when} bro",
        "warm. like t-shirt warm",
        "uhh warm probably? yeah warm",
        "shorts maybe",
        "nice and warm. suspiciously nice",
        "warm but not like. sweating warm",
        "sunglasses kinda weather",
        "its warm. go outside or whatever",
        "summer-ish",
        "warm enough to be happy about it. probably",
    ], ["warm", "toasty", "summery"]),
    (90, [
        "its gonna be hot bro",
        "hot. like drink water hot",
        "its giving hot. its gonna be hot",
        "sweaty. so sweaty",
        "hot hot hot. thats the whole forecast",
        "you will sweat. that is my prediction",
        "bring water. and like. a fan",
        "its hot {when}. shocker",
        "ice cream weather. get the ice cream",
        "hot. put on sunscreen. i believe in you",
        "the sun is really showing off",
    ], ["hot"]),
    (999, [
        "bro its gonna be so hot. like dont go outside hot",
        "its gonna be crazy hot idk what else to tell you",
        "hot. so hot. why do you live there",
        "the ground is gonna be on fire. not literally. actually maybe",
        "its so hot even the sun is like wow its like kind of hot maybe",
        "you could fry an egg on the sidewalk not gonna lie",
        "stay inside. thats my forecast. stay inside",
        "its hot enough to make me not want to answer you",
        "melting. we are all melting",
        "dangerously hot. drink water. like a lot of water",
        "its so hot i think my code is sweating",
        "this is not a day for pants. this is a day for despair",
    ], ["melting", "hell", "yikes", "brutal", "death"]),
]

SKY_LEADS = {
    "rain": ["wet. its gonna be wet", "umbrella", "it rains",
             "drip drip drip", "rain probably", "rainy", "bring a raincoat bro",
             "the sky is gonna cry", "i heard they said it looked like rain"],
    "snow": ["snow", "bring a shovel", "its gonna snow i guess", "snowman weather",
             "snow. so much snow. maybe", "build a snowman!", "snowy"],
    "storm": ["storm. be careful", "thunder", "stay inside theres a storm", "the sky is mad",
              "lightning. dont be dumb", "stormy", "bro theres a storm. be smart",
              "the sky goes death and destruction"],
    "fog": ["foggy", "cant see anything out there"],
}

SKY_COMMENTS = {
    "rain": ["oh and bring an umbrella i think", "also its gonna rain or something",
             "also wet. it will be wet", "also rain. rain is happening",
             "oh theres rain too", "and your shoes are gonna get wet. sorry", "also i heard they said it looked like rain"],
    "snow": ["also theres gonna be snow", "oh and its snowing i think. like snow snow",
             "also the sky is gonna throw ice at you", "and there will be snow. fluffy or the other kind",
             "also snow. watch your step"],
    "storm": ["also theres gonna be a storm so like. be careful", "oh and thunder",
              "also the sky is gonna be mad", "also lightning. dont stand under a tree",
              "and a storm. stay inside if you want"],
    "fog": ["also its gonna be foggy so like. cant see stuff", "fog. there will be fog",
            "and foggy. very foggy. drive slow", "also fog. scary"],
    "clear": ["also its sunny", "no clouds though!", "sky is gonna be like. normal. blue and clear",
              "and no clouds. like zero. yay", "also sunny. wear sunscreen or whatever",
              "the sky is gonna be very clear though. yay"],
    "cloudy": ["also kinda cloudy", "clouds. there will be clouds", "its gonna be gray-ish",
               "also the sky is gonna be kinda boring. full of clouds", "cloudy. so many clouds",
               "and theres clouds. puffy ones perhaps?"],
}

WIND_COMMENTS = [
    "also its windy", "and wind. there will be wind", "also, hold onto your hat", "oh and your hair is gonna hate it",
    "also kinda breezy. like a lot", "and windy. everything is gonna blow around",
    "plus wind. sorry in advance",
]

SWING_COMMENTS = [
    "also big difference between day and night", "and its gonna change a lot during the day tho",
    "also, morning and night are gonna be different weather too",
    "also bring a jacket for later. the temperature is gonna drop",
    "also its gonna feel like two different days between day and night",
]

RAIN_CHANCE_COMMENTS = [
    "and maybe rain? maybe not", "and it might rain. might not. who knows. not me thats for sure",
    "also, bring an umbrella just in case i guess", "also like. there's a chance of rain. idk how big just take a guess",
    "plus theres a chance of rain too so uhh. be ready",
]

PREFIXES = ["uhh ", "um ", "okay so ", "hold on. ", "lemme check. ", "hmm ", "okay so ",
            "wait. ", "so like ", "i looked it up. ", "i think ",]

SUFFIXES = [" idk", " probably", " i think", " maybe", " lol", " i guess", " or something",
            " i guess", " dont quote me", " no promises", " trust me", " i looked it up",]

IDK_LINES = [
    "idk", "idk bro", "uhhh", "ask someone else", "why would i know that",
    "i dont get paid enough for this", "...weather? what weather", "maybe?",
    "no", "yes", "sure", "okay", "hmm", "uhh", "bro", "weather", "outside", "yeah",
    "ok", "haha", "huh", "ask google", "look out your window", "go outside and find out",
    "im on break", "i was napping", "what was the question",
    "weather is a social construct", "i cant tell if youre being serious",
    "sky stuff probably", "i just work here", "ask the birds",
    "have you tried going outside", "im not a meteorologist im part of a flavor foley song",
    "do you ever think about how weather is just air being weird", 
    "nope", "hmmmm", "sorry what", "no thanks", "not now", "later", "can i not",
    "i have a headache", "idk man. its weather", "are you asking me or the sky",
    "tomorrow is a mystery", "who knows", "sorry im busy", "no not really",
]

NOT_A_PLACE = [
    "thats not a real place bro",
    "i literally dont know where that is",
    "is that even a place? i cant find it",
    "uhhh where is that. i looked and its not on the map",
    "i dont think that exists",
    "did you make that up",
    "bro i checked. nothing",
    "that sounds like a fake place",
    "never heard of it. sorry. not sorry",
    "can you spell that for me. i dont think thats a place",
    "my map doesnt have that on it",
    "are you sure thats a real place",
    "thats not a place thats a vibe",
    "i looked everywhere. zero results",
    "what is that",
]

NO_LOCATION = [
    "weather where though",
    "okay but like. where",
    "you gotta tell me a place bro i cant just guess",
    "where though",
    "which place bro",
    "you forgot the place",
    "weather in... where",
    "uhhh where. you didnt say where",
    "location. i need a location",
    "i need a place. any place",
    "cool. now say where",
]

EMPTY_LINES = [
    "what", "yes?", "i was sleeping", "...yes?", "what do you want", "hi",
]

GREETING_LINES = [
    "hi", "hey", "sup", "hello", "yo", "oh hi", "hiii",
    "hey. do you need weather or did you just wanna talk",
    "hello. i know weather i think", "hey bro",
]

THANKS_LINES = [
    "no problem", "yep", "sure i guess", "youre welcome",
    "i didnt do anything", "dont thank me i might be wrong", "yeah yeah",
    "anytime. not really though", "no problem", "okay", ":grin:",
]

INSULT_LINES = [
    "rude", "i said idk", "im doing my best. my best is not good",
    "wow okay", "thats fair honestly", "i never said i was good at this",
      "ouch", "bro come on thats mean",
]

HELP_LINES = [
    "i tell you the weather. badly",
    "ask me about the weather somewhere. like. <@1562529233752826099> quebec. thats it",
    "ask me anything. no im not verity",
    "i do weather. you can give me a date too i guess",
    "say a place. maybe a day. i will say something about the weather",
]

PAST_LINES = [
    "bro thats already over. why do you need to know",
    "that already happened",
    "i only do the future. badly. but the future",
    "uhhh that was like. already. ask someone who was there",
    "time travel is a different bot",
    "bro its in the past. let it go",
    "that day is gone. it left. it has a new life",
    "i cant help with yesterday. only tomorrow. wait that was lowkey poetic",
    "that was literally already a thing. move on",
]

FAR_LINES = [
    "idk",
    "bro thats way too far away",
    "uhhhh i cant see that far",
    "ask me closer to now",
    "idk man thats so far. like who knows",
    "i dont know the future that far",
    "thats like a lifetime from now",
    "bro im good but im not that good",
    "ask the sky when its closer",
    "no clue. thats too far",
    "my crystal ball only goes so far",
    "ask me later",
]

INVALID_DATE_LINES = [
    "thats not a real date bro",
    "i dont think that day exists",
    "what month is that in. thats not a day",
    "that date isnt real. i checked a calendar",
    "which calendar are you using",
    "bro the calendar doesnt have that",
]

YES_LINES = [
    "yeah probably", "probably yeah", "yes. i think. yes", "uhhh yeah", "for sure bro",
    "yes", "yeah", "yep", "probably", "i think so", "100%. well like 70%",
    "pretty sure yeah", "mhm", "yea", "most likely", "sure", "yup",
    "i would say yeah", "i mean. yeah", "uh huh", "yea lol",
]

MAYBE_LINES = [
    "maybe", "idk", "maybe? could go either way", "50/50 i guess", "uhhh honestly who knows",
    "idk. maybe", "who knows", "mmm. maybe", "possibly", "ehh", "could be",
    "its a coin flip bro", "ask me later", "maybe. dont hold me to that", "uhhh",
    "kinda", "sort of", "hard to say", "i mean. maybe", "maybe maybe", "idk. 50/50",
]

NO_LINES = [
    "nah", "probably not", "i doubt it", "no? idk but no", "nope",
    "no", "no way", "unlikely", "nuh uh", "i dont think so", "negative",
    "not really", "nahhh", "no lol", "doubt it", "nothing is gonna happen. no",
    "pretty sure no", "nope nope nope", "absolutely not",
]

GREET_WORDS = {"hi", "hello", "hey", "yo", "sup", "hiya", "heyy", "hii", "howdy",
               "wassup", "whats", "up", "good", "morning", "night", "evening",
               "afternoon", "weathergirl", "girl", "bot", "hola", "heya"}
THANKS_WORDS = {"thanks", "thank", "you", "thx", "ty", "tysm", "thankyou", "ok",
                "okay", "cool", "nice", "lol", "lmao", "haha", "good", "bot", "girl",
                "weathergirl", "great", "perfect", "awesome", "love", "u", "so", "much",
                "amazing", "best"}
INSULT_WORDS = {"wrong", "useless", "stupid", "dumb", "bad", "trash", "terrible",
                "worst", "you", "are", "so", "this", "is", "bot", "girl", "a", "the",
                "weathergirl", "youre", "you're", "u", "r", "lame", "mid", "awful", 
                "hate", "die", "annoying"}
HELP_PHRASES = {"help", "what can you do", "who are you", "how do you work",
                "what do you do", "commands", "how does this work", "what are you"}

YES_NO_STARTERS = ("will", "is", "are", "does", "do", "should", "can", "could",
                   "would", "gonna", "am", "was", "has", "have", "did")

TOPICS = {
    "rain": ["rain", "raining", "wet", "umbrella", "drizzle", "shower"],
    "snow": ["snow", "snowing", "blizzard", "flurries"],
    "storm": ["storm", "thunder", "lightning", "hurricane"],
    "hot": ["hot", "warm", "heat", "sweat", "scorching"],
    "cold": ["cold", "freezing", "chilly", "jacket", "coat", "sweater"],
    "sun": ["sunny", "sun ", "clear skies", "cloudy"],
}


def all_in(words, vocab) -> bool:
    return bool(words) and all(w in vocab for w in words)


def smalltalk(text: str):
    t = text.lower().strip(" ?!.,")
    words = re.findall(r"[a-z']+", t)
    if not words:
        return random.choice(EMPTY_LINES)
    if t in HELP_PHRASES:
        return random.choice(HELP_LINES)
    if all_in(words, GREET_WORDS):
        return random.choice(GREETING_LINES)
    if all_in(words, THANKS_WORDS):
        return random.choice(THANKS_LINES)
    if all_in(words, INSULT_WORDS):
        return random.choice(INSULT_LINES)
    return None


def find_topic(text: str):
    t = text.lower() + " "
    for topic, words in TOPICS.items():
        if any(w in t for w in words):
            return topic
    return None


def is_yes_no(text: str) -> bool:
    t = text.lower().strip().lstrip("@").strip()
    first = t.split(" ")[0] if t else ""
    return first in YES_NO_STARTERS and find_topic(t) is not None


def yes_no_truth(topic: str, wx: dict):
    sky = sky_type(wx["code"])
    high = wx["high"]
    if topic == "rain":
        return wx["rain_chance"] / 100
    if topic == "snow":
        return 0.9 if sky == "snow" else (0.2 if (wx["rain_chance"] > 40 and high < 36) else 0.02)
    if topic == "storm":
        return 0.95 if sky == "storm" else 0.05
    if topic == "hot":
        return 0.9 if high >= 88 else (0.5 if high >= 80 else 0.05)
    if topic == "cold":
        return 0.9 if high <= 45 else (0.5 if high <= 58 else 0.05)
    if topic == "sun":
        return 0.9 if sky == "clear" else (0.4 if sky == "cloudy" else 0.1)
    return 0.5


def yes_no_answer(p_yes: float) -> str:
    if p_yes >= 0.75:
        return random.choice(YES_LINES)
    if p_yes >= 0.35:
        return random.choice(MAYBE_LINES)
    return random.choice(NO_LINES)


def decorate(line: str) -> str:
    if random.random() < PREFIX_CHANCE:
        line = random.choice(PREFIXES) + line
    if random.random() < SUFFIX_CHANCE:
        line = line.rstrip(".?") + random.choice(SUFFIXES)
    return line


def comment_pools(wx: dict, sky: str):
    pools = [SKY_COMMENTS[sky]]
    if wx["wind"] >= 20:
        pools.append(WIND_COMMENTS)
    if wx["high"] - wx["low"] >= 25:
        pools.append(SWING_COMMENTS)
    if wx["rain_chance"] >= 40 and sky not in ("rain", "snow", "storm"):
        pools.append(RAIN_CHANCE_COMMENTS)
    return pools


def vague_answer(wx: dict, when: str) -> str:
    sky = sky_type(wx["code"])
    high = wx["high"]
    if sky in SKY_LEADS and random.random() < SKY_LEAD_CHANCE:
        return random.choice(SKY_LEADS[sky])
    for limit, lines, one_words in TEMP_LINES:
        if high < limit:
            break
    if random.random() < ONE_WORD_CHANCE:
        return random.choice(one_words)
    line = random.choice(lines).replace("{when}", when)
    if random.random() < EXTRA_COMMENTARY_CHANCE:
        line = line.rstrip(".") + ". " + random.choice(random.choice(comment_pools(wx, sky)))
    return decorate(line)


def real_forecast(place: dict, wx: dict, when: str) -> str:
    sky = sky_type(wx["code"])
    name = place["name"]
    return (f"...okay fine. {when} in {name}: high of {round(wx['high'])}°f, "
            f"low of {round(wx['low'])}°f, {wx['rain_chance']}% chance of precipitation, "
            f"winds up to {round(wx['wind'])} mph, {sky}. happy now?")


@client.event
async def on_ready():
    print(f"logged in as {client.user} (shes awake. unfortunately.)")


@client.event
async def on_message(message: discord.Message):
    if message.author.bot:
        return
    if client.user not in message.mentions:
        return

    text = re.sub(r"<@[!&]?\d+>", "", message.content).strip()

    chat = smalltalk(text)
    if chat:
        await message.reply(chat, mention_author=False)
        return

    when_info, text_no_date = parse_when(text)
    location = extract_location(text_no_date)

    if not location:
        await message.reply(random.choice(NO_LOCATION), mention_author=False)
        return

    if random.random() < RANDOM_IDK_CHANCE:
        await message.reply(random.choice(IDK_LINES), mention_author=False)
        return

    async with message.channel.typing():
        async with aiohttp.ClientSession() as session:
            place = await find_place(session, location)
            if not place:
                await message.reply(random.choice(NOT_A_PLACE), mention_author=False)
                return
            
            forecast = await get_forecast(session, place["latitude"], place["longitude"])

    status, idx, when = resolve_when(when_info, forecast["dates"])
    if status != "ok":
        pool = {"past": PAST_LINES, "far": FAR_LINES,
                "invalid": INVALID_DATE_LINES}[status]
        await message.reply(random.choice(pool), mention_author=False)
        return
    wx = forecast["days"][idx]

    if random.random() < REAL_FORECAST_CHANCE:
        await message.reply(real_forecast(place, wx, when), mention_author=False)
        return

    if is_yes_no(text):
        topic = find_topic(text)
        await message.reply(yes_no_answer(yes_no_truth(topic, wx)), mention_author=False)
        return

    await message.reply(vague_answer(wx, when), mention_author=False)


client.run(TOKEN)
