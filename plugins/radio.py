# plugins/radio.py
from __future__ import annotations

from typing import Any, Dict, List

PLUGIN_NAME = "radio"

def cmd_noise(bot, packet: Dict[str, Any], sender_key: str, args: List[str]):
    snr = packet.get("rxSnr")
    rssi = packet.get("rxRssi")

    if snr is None or rssi is None:
        return "📡 Noise floor: unavailable (rxSnr/rxRssi missing in this packet)"

    try:
        noise = float(rssi) - float(snr)
    except Exception:
        return "📡 Noise floor: unavailable (could not parse rxSnr/rxRssi)"

    # rssi is typically dBm, snr is dB -> noise is roughly dBm
    return f"📡 Noise floor (est.): {noise:.1f} dBm | RSSI {rssi} dBm | SNR {snr} dB"

COMMANDS = {
    "noise": {
        "help": "Estimate noise floor using RSSI - SNR from the last received packet.",
        "usage": "!noise",
        "handler": cmd_noise,
    },
}
