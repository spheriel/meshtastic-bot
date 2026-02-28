# 🛰️ Meshtastic Channel Utility Bot

Lightweight multi‑purpose Meshtastic utility bot designed to run on a
Raspberry Pi connected to a Meshtastic device (e.g. Heltec T114) over
USB.

The bot listens and responds **only on a specific channel** (default
`channelIndex = 1`), making it ideal for private groups,
custom‑frequency networks, and experimental mesh deployments.

------------------------------------------------------------------------
## Installation
    git clone https://github.com/spheriel/meshtastic-bot
    cd meshtastic-bot
    chmod u+x install.sh
    ./install.sh

## Note
    Autostart after reboot is enabled automatically.

## ✨ Features

-   `!help` --- command list\
-   `!ping` --- connectivity test (+ RSSI / SNR if available)\
-   `!whoami` --- identify sender node\
-   `!nodes` --- list known nodes\
-   `!uptime` --- bot + system uptime\
-   `!weather <city>` --- current weather\
-   `!msg <node> <text>` --- store‑and‑forward messaging\
-   `!inbox` --- retrieve waiting messages\
-   `!air` --- airtime + channel utilization stats

------------------------------------------------------------------------

## 📡 Airtime Metrics Explained

`!air` returns:

  Metric   Meaning
  -------- ----------------------------
  TX       your node transmit airtime
  RX       receive airtime
  CH       total channel utilization

------------------------------------------------------------------------

## 🎯 Design Goals

-   simple
-   stable
-   headless friendly
-   zero database
-   config‑file driven
-   safe for private mesh networks

------------------------------------------------------------------------

## 🖥 Typical Setup

Hardware: - Raspberry Pi - Meshtastic device - USB cable

Software: - Python 3.11+ - meshtastic - requests

------------------------------------------------------------------------

## ⚙ Configuration

Configured via:

    config.toml

Example:

    device = "/dev/ttyACM0"
    channel_index = 1

------------------------------------------------------------------------

## 🚀 Run

    python3 meshtastic_bot.py --config config.toml

Recommended production run: systemd service.

------------------------------------------------------------------------

## 🔒 Channel Isolation

Bot processes messages **only on configured channel index**, preventing
accidental interaction with public mesh traffic.

------------------------------------------------------------------------

## 📜 Regulatory Notice

Supports EU bands:

  Band                Duty Cycle
  ------------------- ------------
  868 MHz default     1%
  869.4--869.65 MHz   10%

Always follow local radio regulations.

------------------------------------------------------------------------

## 🧪 Example Use Cases

-   private mesh assistant
-   diagnostics node
-   gateway monitor
-   field network helper
-   experimental high‑traffic node

------------------------------------------------------------------------

## 📄 License

MIT.

------------------------------------------------------------------------

**Happy meshing 📡**
