#!/usr/bin/env python3
from __future__ import annotations

import argparse
import time
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import requests

# ----------------------------
# PubSub compatibility hotfix
# ----------------------------
from pubsub import pub as _pub  # noqa

_orig_send = _pub.sendMessage

def _sendMessage_compat(topicName, **msgData):
    """
   meshtastic 2.7.7 often publishes interface, but PyPubSub topic specs (and most listeners) expect iface. We remap this for all events starting with meshtastic.
    """
    if isinstance(topicName, str) and topicName.startswith("meshtastic."):
        if "interface" in msgData and "iface" not in msgData:
            msgData["iface"] = msgData.pop("interface")
    return _orig_send(topicName, **msgData)

_pub.sendMessage = _sendMessage_compat
# ----------------------------

import meshtastic  # noqa: E402
import meshtastic.serial_interface  # noqa: E402
from pubsub import pub  # noqa: E402

try:
    import tomllib  # py3.11+
except Exception:  # pragma: no cover
    tomllib = None


# ----------------------------
# Utilities
# ----------------------------

def now_ts() -> float:
    return time.time()

def clamp(s: str, n: int) -> str:
    if len(s) <= n:
        return s
    return s[: max(0, n - 1)] + "…"

def format_duration(seconds: float) -> str:
    seconds = int(seconds)
    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    seconds %= 60
    parts = []
    if days: parts.append(f"{days}d")
    if hours: parts.append(f"{hours}h")
    if minutes: parts.append(f"{minutes}m")
    parts.append(f"{seconds}s")
    return " ".join(parts)

def safe_get(d: Dict[str, Any], path: List[str], default=None):
    cur: Any = d
    for p in path:
        if not isinstance(cur, dict) or p not in cur:
            return default
        cur = cur[p]
    return cur

def fmt_pct(x: Any) -> str:
    if x is None:
        return "?"
    try:
        # někdy je to int, někdy float, někdy string
        v = float(x)
        # typicky stačí 1 desetinné místo
        if abs(v - round(v)) < 1e-9:
            return f"{int(round(v))}%"
        return f"{v:.1f}%"
    except Exception:
        return "?"


# ----------------------------
# Config
# ----------------------------

@dataclass
class Config:
    device: str
    channel_index: int
    command_prefix: str
    max_reply_len: int
    mailbox_ttl_seconds: int
    weather_units: str
    weather_lang: str
    weather_default_place: str

def load_config(path: str) -> Config:
    if tomllib is None:
        raise RuntimeError("tomllib not available (Python 3.11+ required).")

    with open(path, "rb") as f:
        raw = tomllib.load(f)

    device = raw.get("meshtastic", {}).get("device", "/dev/ttyUSB0")
    channel_index = int(raw.get("meshtastic", {}).get("channel_index", 1))

    bot = raw.get("bot", {})
    command_prefix = str(bot.get("command_prefix", "!"))
    max_reply_len = int(bot.get("max_reply_len", 220))
    mailbox_ttl_seconds = int(bot.get("mailbox_ttl_seconds", 7 * 24 * 3600))

    weather = raw.get("weather", {})
    weather_units = str(weather.get("units", "metric"))
    weather_lang = str(weather.get("lang", "cs"))
    weather_default_place = str(weather.get("default_place", "Prague"))

    if weather_units not in ("metric", "imperial"):
        raise ValueError("weather.units must be 'metric' or 'imperial'")

    return Config(
        device=device,
        channel_index=channel_index,
        command_prefix=command_prefix,
        max_reply_len=max_reply_len,
        mailbox_ttl_seconds=mailbox_ttl_seconds,
        weather_units=weather_units,
        weather_lang=weather_lang,
        weather_default_place=weather_default_place,
    )


# ----------------------------
# Mailbox
# ----------------------------

@dataclass
class PendingMessage:
    created_ts: float
    from_display: str
    text: str

class Mailbox:
    def __init__(self, ttl_seconds: int):
        self.ttl_seconds = ttl_seconds
        self._store: Dict[str, List[PendingMessage]] = {}

    def _purge(self):
        cutoff = now_ts() - self.ttl_seconds
        for k in list(self._store.keys()):
            msgs = [m for m in self._store[k] if m.created_ts >= cutoff]
            if msgs:
                self._store[k] = msgs
            else:
                self._store.pop(k, None)

    def add(self, dest_key: str, msg: PendingMessage):
        self._purge()
        self._store.setdefault(dest_key, []).append(msg)

    def get_for(self, dest_key: str) -> List[PendingMessage]:
        self._purge()
        return list(self._store.get(dest_key, []))

    def pop_for(self, dest_key: str) -> List[PendingMessage]:
        self._purge()
        return self._store.pop(dest_key, [])


# ----------------------------
# Weather (Open-Meteo)
# ----------------------------

WMO_MAP = {
    0: "clear",
    1: "mostly clear",
    2: "partly cloudy",
    3: "overcast",
    45: "fog",
    48: "rime fog / freezing fog",
    51: "light drizzle",
    53: "drizzle",
    55: "heavy drizzle",
    56: "light freezing drizzle",
    57: "freezing drizzle",
    61: "light rain",
    63: "rain",
    65: "heavy rain",
    66: "light freezing rain",
    67: "freezing rain",
    71: "light snow",
    73: "snow",
    75: "heavy snow",
    77: "snow grains",
    80: "light showers",
    81: "showers",
    82: "heavy showers",
    85: "light snow showers",
    86: "snow showers",
    95: "thunderstorm",
    96: "thunderstorm with hail",
    99: "severe thunderstorm with hail",
}

def weather_text(code: Optional[int]) -> str:
    if code is None:
        return "unknown"
    return WMO_MAP.get(int(code), f"kód {code}")

def fetch_weather(place: str, units: str) -> str:
    geo_url = "https://geocoding-api.open-meteo.com/v1/search"
    g = requests.get(
        geo_url,
        params={"name": place, "count": 1, "language": "cs", "format": "json"},
        timeout=10,
    )
    g.raise_for_status()
    gj = g.json()
    results = gj.get("results") or []
    if not results:
        return f"❌ Location not found: {place}"

    r0 = results[0]
    lat = r0["latitude"]
    lon = r0["longitude"]
    name = r0.get("name", place)
    country = r0.get("country", "")

    wx_url = "https://api.open-meteo.com/v1/forecast"
    params = {
        "latitude": lat,
        "longitude": lon,
        "current": "temperature_2m,apparent_temperature,wind_speed_10m,weather_code",
    }
    if units == "imperial":
        params.update({"temperature_unit": "fahrenheit", "wind_speed_unit": "mph"})
    else:
        params.update({"temperature_unit": "celsius", "wind_speed_unit": "kmh"})

    w = requests.get(wx_url, params=params, timeout=10)
    w.raise_for_status()
    wj = w.json()
    cur = wj.get("current") or {}

    t = cur.get("temperature_2m")
    feels = cur.get("apparent_temperature")
    wind = cur.get("wind_speed_10m")
    code = cur.get("weather_code")

    t_unit = "°F" if units == "imperial" else "°C"
    w_unit = "mph" if units == "imperial" else "km/h"

    return (
        f"🌦️ {name}{(', ' + country) if country else ''}: "
        f"{t}{t_unit} (feels like {feels}{t_unit}), {weather_text(code)}, wind {wind} {w_unit}"
    )


# ----------------------------
# Meshtastic bot
# ----------------------------

class MeshBot:
    def __init__(self, cfg: Config):
        self.cfg = cfg
        self.started_ts = now_ts()
        self.mailbox = Mailbox(ttl_seconds=cfg.mailbox_ttl_seconds)
        self.iface = meshtastic.serial_interface.SerialInterface(devPath=cfg.device)

    def run(self):
        pub.subscribe(self.on_receive, "meshtastic.receive")
        pub.subscribe(self.on_connection, "meshtastic.connection.established")
        print(f"[+] Bot running. Device={self.cfg.device}, channelIndex={self.cfg.channel_index}")
        try:
            while True:
                time.sleep(3600)
        except KeyboardInterrupt:
            print("\n[!] Končím…")
        finally:
            try:
                self.iface.close()
            except Exception:
                pass

    # tolerant signature for compatibility with different topic args
    def on_connection(self, iface=None, interface=None, **kwargs):
        return

    def send_channel(self, text: str):
        text = clamp(text, self.cfg.max_reply_len)
        self.iface.sendText(text, channelIndex=self.cfg.channel_index)

    def lookup_node_name(self, node_key: str) -> Optional[str]:
        try:
            nodes = getattr(self.iface, "nodes", {}) or {}
            n = nodes.get(node_key)
            if not n:
                for k, v in nodes.items():
                    uid = safe_get(v, ["user", "id"])
                    if uid == node_key:
                        n = v
                        break
            if not n:
                return None
            long_name = safe_get(n, ["user", "longName"])
            short_name = safe_get(n, ["user", "shortName"])
            return short_name or long_name
        except Exception:
            return None

    def resolve_target(self, token: str) -> Tuple[Optional[str], Optional[str]]:
        token = token.strip()
        nodes = getattr(self.iface, "nodes", {}) or {}

        if re.fullmatch(r"![0-9a-fA-F]{8}", token):
            name = self.lookup_node_name(token.lower())
            return token.lower(), name

        token_l = token.lower()
        for k, v in nodes.items():
            long_name = (safe_get(v, ["user", "longName"]) or "").strip()
            short_name = (safe_get(v, ["user", "shortName"]) or "").strip()
            if long_name.lower() == token_l or short_name.lower() == token_l:
                return str(k), (short_name or long_name or None)

        return None, None

    def packet_channel_index(self, packet: Dict[str, Any]) -> Optional[int]:
        for path in (["channel"], ["decoded", "channel"], ["decoded", "channelIndex"], ["rx", "channel"]):
            v = safe_get(packet, path)
            if v is not None:
                try:
                    return int(v)
                except Exception:
                    pass
        return None

    # -------- NEW: local airtime metrics (robust across versions) --------
    def get_local_airtime_metrics(self) -> Tuple[Optional[Any], Optional[Any], Optional[Any]]:
        """
        Returns (airUtilTx, airUtilRx, channelUtilization) for the local node.
        Different versions store metrics differently, so we try multiple paths.
        """
        candidates: List[Dict[str, Any]] = []

        # 1) getMyNodeInfo (if available)
        try:
            mi = self.iface.getMyNodeInfo()
            if isinstance(mi, dict):
                candidates.append(mi)
        except Exception:
            pass

        # 2) localNode (some versions)
        try:
            ln = getattr(self.iface, "localNode", None)
            if isinstance(ln, dict):
                candidates.append(ln)
        except Exception:
            pass

        # 3) self.iface.nodes by local node key
        try:
            nodes = getattr(self.iface, "nodes", {}) or {}

            # try nodeNum -> !xxxxxxxx
            my_node_num = None
            my_info = getattr(self.iface, "myInfo", None)
            if isinstance(my_info, dict):
                my_node_num = my_info.get("my_node_num") or my_info.get("myNodeNum") or my_info.get("nodeNum")

            if my_node_num is not None:
                try:
                    key = f"!{int(my_node_num):08x}"
                    n = nodes.get(key)
                    if isinstance(n, dict):
                        candidates.append(n)
                except Exception:
                    pass

            # fallback: if a node with user.isLocal exists
            for _k, v in nodes.items():
                if safe_get(v, ["user", "isLocal"]) is True:
                    if isinstance(v, dict):
                        candidates.append(v)
                        break
        except Exception:
            pass

        # extract metrics from candidates
        for c in candidates:
            # most commonly deviceMetrics
            tx = safe_get(c, ["deviceMetrics", "airUtilTx"])
            rx = safe_get(c, ["deviceMetrics", "airUtilRx"])
            ch = safe_get(c, ["deviceMetrics", "channelUtilization"])
            if tx is not None or rx is not None or ch is not None:
                return tx, rx, ch

            # sometimes telemetry -> deviceMetrics
            tx = safe_get(c, ["telemetry", "deviceMetrics", "airUtilTx"])
            rx = safe_get(c, ["telemetry", "deviceMetrics", "airUtilRx"])
            ch = safe_get(c, ["telemetry", "deviceMetrics", "channelUtilization"])
            if tx is not None or rx is not None or ch is not None:
                return tx, rx, ch

            # sometimes in 'metrics' (less common)
            tx = safe_get(c, ["metrics", "airUtilTx"])
            rx = safe_get(c, ["metrics", "airUtilRx"])
            ch = safe_get(c, ["metrics", "channelUtilization"])
            if tx is not None or rx is not None or ch is not None:
                return tx, rx, ch

        return None, None, None
    # --------------------------------------------------------------------

    # tolerant signature
    def on_receive(self, packet=None, iface=None, interface=None, **kwargs):
        if not isinstance(packet, dict):
            return

        decoded = packet.get("decoded") or {}
        text = decoded.get("text")

        ch = self.packet_channel_index(packet)
        if ch is None or ch != self.cfg.channel_index:
            return

        # mailbox delivery on any activity on channel 1
        self.maybe_deliver_mailbox(packet)

        if not isinstance(text, str) or not text.strip():
            return

        text = text.strip()
        if not text.startswith(self.cfg.command_prefix):
            return

        sender_key = packet.get("fromId") or packet.get("from")
        if isinstance(sender_key, int):
            sender_key = f"!{sender_key:08x}"
        sender_key = str(sender_key) if sender_key is not None else "unknown"

        cmdline = text[len(self.cfg.command_prefix):].strip()
        if not cmdline:
            return
        parts = cmdline.split()
        cmd = parts[0].lower()
        args = parts[1:]

        try:
            if cmd in ("help", "?"):
                self.cmd_help()
            elif cmd == "ping":
                self.cmd_ping(packet)
            elif cmd == "whoami":
                self.cmd_whoami(sender_key)
            elif cmd == "nodes":
                self.cmd_nodes()
            elif cmd == "uptime":
                self.cmd_uptime()
            elif cmd == "weather":
                self.cmd_weather(args)
            elif cmd == "air":  # NEW
                self.cmd_air()
            elif cmd == "msg":
                self.cmd_msg(sender_key, args)
            elif cmd == "inbox":
                self.cmd_inbox(sender_key)
            else:
                self.send_channel(f"❓ Unknown command '{cmd}'. Try !help")
        except requests.RequestException as e:
            self.send_channel(f"❌ Network error: {type(e).__name__}")
        except Exception as e:
            self.send_channel(f"❌ Error: {type(e).__name__}")

    def maybe_deliver_mailbox(self, packet: Dict[str, Any]):
        sender_key = packet.get("fromId") or packet.get("from")
        if isinstance(sender_key, int):
            sender_key = f"!{sender_key:08x}"
        sender_key = str(sender_key) if sender_key is not None else None
        if not sender_key:
            return

        pending = self.mailbox.pop_for(sender_key)
        if not pending:
            return

        dest_name = self.lookup_node_name(sender_key) or sender_key
        for m in pending:
            age = format_duration(now_ts() - m.created_ts)
            self.send_channel(f"📮 For {dest_name}: from {m.from_display} ({age}): {m.text}")

    # ----------------------------
    # Commands
    # ----------------------------

    def cmd_help(self):
        self.send_channel(
            "🤖 Commands: "
            "!help, !ping, !whoami, !nodes, !uptime, "
            "!weather [place], "
            "!air, "
            "!msg <cílový_node|!hexid|shortName|longName> <text>, "
            "!inbox"
        )

    def cmd_ping(self, packet: Dict[str, Any]):
        snr = packet.get("rxSnr")
        rssi = packet.get("rxRssi")
        extras = []
        if snr is not None:
            extras.append(f"SNR {snr}")
        if rssi is not None:
            extras.append(f"RSSI {rssi}")
        extra_txt = (" (" + ", ".join(extras) + ")") if extras else ""
        self.send_channel("pong 🏓" + extra_txt)

    def cmd_whoami(self, sender_key: str):
        name = self.lookup_node_name(sender_key)
        disp = f"{name} ({sender_key})" if name else sender_key
        self.send_channel(f"You are: {disp}")

    def cmd_nodes(self):
        nodes = getattr(self.iface, "nodes", {}) or {}
        count = len(nodes)
        names: List[str] = []
        for k, v in list(nodes.items())[:8]:
            short_name = safe_get(v, ["user", "shortName"])
            long_name = safe_get(v, ["user", "longName"])
            nm = (short_name or long_name or str(k))
            names.append(str(nm))
        tail = (" | " + ", ".join(names)) if names else ""
        self.send_channel(f"📡 Nodes: {count}{tail}")

    def cmd_uptime(self):
        bot_uptime = format_duration(now_ts() - self.started_ts)
        sys_uptime = None
        try:
            with open("/proc/uptime", "r", encoding="utf-8") as f:
                sys_uptime = float(f.read().split()[0])
        except Exception:
            pass

        if sys_uptime is not None:
            self.send_channel(f"⏱️ Uptime: bot {bot_uptime}, system {format_duration(sys_uptime)}")
        else:
            self.send_channel(f"⏱️ Uptime: bot {bot_uptime}")

    def cmd_weather(self, args: List[str]):
        place = " ".join(args).strip()
        if not place:
            place = self.cfg.weather_default_place
        txt = fetch_weather(place, self.cfg.weather_units)
        self.send_channel(txt)

    def cmd_air(self):
        tx, rx, ch = self.get_local_airtime_metrics()
        if tx is None and rx is None and ch is None:
            self.send_channel("📡 Airtime: metrics not available (enable telemetry on the node, or wait for an update).")
            return
        self.send_channel(f"📡 Airtime: TX {fmt_pct(tx)} | RX {fmt_pct(rx)} | CH {fmt_pct(ch)}")

    def cmd_msg(self, sender_key: str, args: List[str]):
        if len(args) < 2:
            self.send_channel("Usage: !msg <cílový_node|!hexid|shortName|longName> <text>")
            return

        target_token = args[0]
        message_text = " ".join(args[1:]).strip()
        if not message_text:
            self.send_channel("❌ Missing message text.")
            return

        target_key, target_name = self.resolve_target(target_token)
        if not target_key:
            self.send_channel(f"❌ Cannot find node '{target_token}'. Try !nodes for a list.")
            return

        from_disp = self.lookup_node_name(sender_key)
        from_display = f"{from_disp}({sender_key})" if from_disp else sender_key

        self.mailbox.add(
            target_key,
            PendingMessage(created_ts=now_ts(), from_display=from_display, text=clamp(message_text, 400)),
        )

        pretty_target = target_name or target_key
        self.send_channel(
            f"✅ Saved to mailbox for {pretty_target}. "
            f"Will deliver when active on channel {self.cfg.channel_index}."
        )

    def cmd_inbox(self, sender_key: str):
        msgs = self.mailbox.get_for(sender_key)
        if not msgs:
            self.send_channel("📭 Inbox: empty.")
            return
        lines = []
        for m in msgs[:3]:
            age = format_duration(now_ts() - m.created_ts)
            lines.append(f"- od {m.from_display} ({age}): {clamp(m.text, 80)}")
        more = f" (+{len(msgs)-3} more)" if len(msgs) > 3 else ""
        self.send_channel("📬 Inbox:\n" + "\n".join(lines) + more)


def main():
    ap = argparse.ArgumentParser(description="Meshtastic channel utility bot")
    ap.add_argument("-c", "--config", default="config.toml", help="Path to config.toml")
    args = ap.parse_args()

    cfg = load_config(args.config)
    bot = MeshBot(cfg)
    bot.run()


if __name__ == "__main__":
    main()
