# weathergirl
> a discord bot that technically tells you the weather sometimes

ask her about the weather somewhere and she'll say something like "uhhh... cold probably. idk". she checks the real forecast first, so she won't say it's freezing somewhere that's actually hot. about 10% of the time she gives you the real forecast, but she's maybe a bit upset about it.

loosely inspired by the song "weathergirl" by flavor foley. minus the personality

**[add her to your server!](<https://discord.com/oauth2/authorize?client_id=1562529233752826099&permissions=68608&integration_type=0&scope=bot>)**

---

## what she sounds like

```
you:  @weathergirl what will the weather be tomorrow in quebec
her:  uhhh... cold probably. idk

you:  @weathergirl south florida
her:  its gonna be warm tomorrow bro

you:  @weathergirl will it rain in seattle friday
her:  maybe

you:  @weathergirl what about uae
her:  ...okay fine. tomorrow in United Arab Emirates: high of 100°f, low of 75°f, 0% 
chance of precipitation, winds up to 10 mph, clear. happy now?
```

---

## how to talk to her

mention her, then say a place and (if you want) a day.

| you say | she does |
| --- | --- |
| `@weathergirl [place]` | forecast for tomorrow |
| `@weathergirl weather in [place] today` | forecast for today |
| `@weathergirl [place] on [day]` | forecast for the next [day] |
| `@weathergirl [place] [date]` | forecast for that date, if it's close enough |
| `@weathergirl will it [action] in [place]` | a yes/no answer |
| `@weathergirl help` | explains herself, badly |

dates in the past get an... interesting reply, dates too far away get an "idk", and places she can't find get something along the lines of, "that's not a real place." there's a few additional keywords she responds to, such as blank messages with a mention, thank you mesaages, and certain insulting messages.

---

## what she can do

- **answers** - every reply matches to the forecast, so temperature, rain, snow, storms, fog, and wind. different aspects of the forecast have a different percentage chance of being in her message. 
- **understands dates** - `tomorrow`, `today`, `tonight`, `friday`, `october 25`, `oct 25th`, `25 october`, `10/25`, `25/10`. anything more than about 16 days out gets an "idk". she understands both dd/mm formatting and mm/dd formatting, just keep in mind that if you want to find may 11, you'd type in 5/11 or 11/05 (or 11/5), and if you want to find november 5 you'd type in 11/5 (or 11/05) or 05/11. if you're using dd/mm for a date that has a smaller day than month, put a zero in the front of it. 
- **answers yes/no question** - "will it rain?" gets "probably", "maybe", or "nah", based on the real chances.
- **sometimes uses one word** - "warm." "freezing."  idk why she's trying to vaguepost but okay i guess
- **has a personality** - she shrugs, gets distracted, and adds random comments sometimes
- **makes small talk.** say hi, say thanks, insult her (if you're mean) or ask for `help`.

---

## trouble?

**she's not replying.** make sure she can see and send messages in that channel, and that you actually @mention her (pick her from the popup so it turns into a blue name or reply to her with the @mention on). if she's still quiet, she might be offline.

**she says a real place isn't real.** try just the city name (for example, `austin`) instead of `austin texas`. the lookup works by name, and extra state or country words can confuse it.

**she's wrong about the weather.** she isn't supposed to be wrong, just vague. forecasts can change, though, so check again closer to the day.




---

## files

```
weathergirl/
  bot.py              the whole bot
  requirements.txt    libraries
  .env                token (keep out of git)
  .gitignore          hides .env and venv from git
```

---

## made with

[discord.py](https://github.com/Rapptz/discord.py) / [aiohttp](https://github.com/aio-libs/aiohttp) / [python-dotenv](https://github.com/theskumar/python-dotenv) / [open-meteo](https://open-meteo.com/)