# plugins/diagnostics.py
from __future__ import annotations

import time
from typing import Any, Dict, List

PLUGIN_NAME = "diagnostics"

def _fmt_age(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes}m"
    hours = minutes // 60
    minutes %= 60
    if hours < 24:
        return f"{hours}h {minutes}m"
    days = hours // 24
    hours %= 24
    return f"{days}d {hours}h"

def cmd_snr(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    snr = packet.get("rxSnr")
    rssi = packet.get("rxRssi")
    return f"📶 SNR: {snr if snr is not None else '?'} | RSSI: {rssi if rssi is not None else '?'}"

def cmd_route(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    rx_hops = packet.get("rxHop") or packet.get("hops") or packet.get("hopCount")
    hop_limit = packet.get("hopLimit")
    if rx_hops is not None:
        return f"🧭 Route: {rx_hops} hops"
    if hop_limit is not None:
        return f"🧭 Hop limit: {hop_limit}"
    return "🧭 Route: (no hop info in packet)"

def cmd_seen(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    target = sender_key
    if args:
        token = " ".join(args).strip()
        try:
            key, _name = bot.resolve_target(token)
            target = key or token
        except Exception:
            target = token

    seen = bot.state.get("seen", {})
    ts = seen.get(target)
    if ts is None:
        return f"👀 Seen: {target} — never (in this bot session)"
    age = _fmt_age(time.time() - float(ts))
    return f"👀 Seen: {target} — {age} ago"

def cmd_load(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    _tx, _rx, ch = bot.get_local_airtime_metrics()
    if ch is None:
        return "📡 Channel load: unknown"
    try:
        v = float(ch)
    except Exception:
        return "📡 Channel load: unknown"

    if v < 1.0:
        label = "IDLE"
    elif v < 5.0:
        label = "OK"
    elif v < 15.0:
        label = "BUSY"
    else:
        label = "CONGESTED"
    return f"📡 Channel load: {label} (CH {v:.1f}%)"

COMMANDS = {
    "snr": {
        "help": "Show SNR/RSSI for the last received packet.",
        "usage": "!snr",
        "handler": cmd_snr,
    },
    "route": {
        "help": "Show hop/route info if present in the packet.",
        "usage": "!route",
        "handler": cmd_route,
    },
    "seen": {
        "help": "Show when a node was last seen (in this bot session).",
        "usage": "!seen [node]",
        "handler": cmd_seen,
    },
    "load": {
        "help": "Interpret channel utilization (from !air metrics).",
        "usage": "!load",
        "handler": cmd_load,
    },
}
