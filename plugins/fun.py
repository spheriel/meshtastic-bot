# plugins/fun.py
from __future__ import annotations

import random
from typing import Any, Dict, List

PLUGIN_NAME = "fun"

_8BALL = [
    "It is certain.",
    "Without a doubt.",
    "Yes — definitely.",
    "Most likely.",
    "Ask again later.",
    "Cannot predict now.",
    "Don't count on it.",
    "My reply is no.",
    "Very doubtful.",
]

def cmd_roll(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    sides = 6
    if args:
        try:
            sides = int(args[0])
        except Exception:
            return "Usage: !roll [sides]"
    if sides < 2 or sides > 1000:
        return "Usage: !roll [2..1000]"
    return f"🎲 d{sides}: {random.randint(1, sides)}"

def cmd_8ball(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    return f"🎱 {_8BALL[random.randrange(len(_8BALL))]}"

def cmd_stats(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    c = bot.state.get("counters", {})
    seen = bot.state.get("seen", {})
    return (
        f"📊 Stats: messages={int(c.get('messages_seen', 0))}, "
        f"commands={int(c.get('commands_executed', 0))}, "
        f"unique_nodes={len(seen)}"
    )

COMMANDS = {
    "roll": {
        "help": "Roll a dice (default d6).",
        "usage": "!roll [sides]",
        "handler": cmd_roll,
    },
    "8ball": {
        "help": "Magic 8-ball answer.",
        "usage": "!8ball",
        "handler": cmd_8ball,
    },
    "stats": {
        "help": "Bot usage stats (this session).",
        "usage": "!stats",
        "handler": cmd_stats,
    },
}
