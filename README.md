# 🛰️ Meshtastic Channel Utility Bot

Lightweight multi‑purpose Meshtastic utility bot designed to run on a
Raspberry Pi connected to a Meshtastic device (e.g. Heltec T114) over
USB.

The bot listens and responds **only on a specific channel** (default
`channelIndex = 1`), making it ideal for private groups,
custom‑frequency networks, and experimental mesh deployments.

------------------------------------------------------------------------

# Features

### Core commands
| Command | Description |
|--------|-------------|
!help | Show command list |
!ping | Connectivity test |
!whoami | Show your node ID |
!nodes | List visible nodes |
!uptime | Bot + system uptime |
!weather [place] | Current weather |
!air | Airtime usage metrics |
!msg <node> <text> | Leave offline message |
!inbox | Show stored messages |

---

### Plugin commands
Plugins extend functionality automatically when placed inside the `plugins/` folder.

Included examples:

#### Diagnostics plugin
| Command | Description |
|--------|-------------|
!snr | Show SNR/RSSI |
!route | Packet hop info |
!seen | Last seen time |
!load | Channel load status |

#### Fun plugin
| Command | Description |
|--------|-------------|
!roll [n] | Roll dice |
!8ball | Magic 8‑ball |
!stats | Bot statistics |

---

# Plugin System

The bot automatically loads plugins from:

```
plugins/
```

Each plugin is a `.py` file containing:

```
COMMANDS = { ... }
```

Command handler signature:

```
def handler(bot, packet, sender_key, args):
    return "response text"
```

Optional:

```
PLUGIN_NAME = "name"
def register(bot): ...
```

Plugins are loaded at startup. No restart logic or registration needed.

If a plugin fails to load, the bot continues running.

---

# Installation

Install python prerequisites:
```
sudo apt install -y python3 python3-venv python3-pip git
```

Add user to the dialout group and reboot:
```
sudo usermod -aG dialout $USER
reboot
```

Clone repository:

```
git clone <repo>
cd <repo>
```

Run installer:

```
chmod u+x install.sh
./install.sh
```

Service commands:

```
systemctl --user status meshtastic-bot
systemctl --user restart meshtastic-bot
```

Enable autostart:

```
Autostart after reboot should be enabled automatically. If not you can do it by:
sudo loginctl enable-linger $USER
```

---

# Configuration

Edit:

```
config.toml
```

Important settings:

| Setting | Meaning |
|--------|--------|
device | serial port |
channel_index | channel bot listens on |
command_prefix | command symbol |
max_reply_len | LoRa message limit |

---

# Versioning

Releases follow semantic versioning:

```
MAJOR.MINOR.PATCH
```

Examples:

- v1.0 → initial release
- v1.1 → plugin system
- v1.1.1 → bugfix

Download specific version:

```
git checkout v1.0
```

---

# Safety Notes

The bot transmits over LoRa. Respect local duty‑cycle regulations.

Airtime command:

```
!air
```

Shows:

- TX %
- RX %
- Channel usage %

---

# Architecture

Core bot handles:

- radio interface
- command parsing
- mailbox
- telemetry
- plugin loader

Plugins handle:

- optional commands
- extensions
- experiments

This separation keeps the core stable and extensible.

---

# Creating a Plugin

Example:

```
# plugins/hello.py

def hello(bot, packet, sender, args):
    return "Hello world"

COMMANDS = {
    "hello": {
        "help": "Test command",
        "handler": hello
    }
}
```

Restart bot → command available instantly.

---

# License
See LICENSE file.

---

# Author
Created for Meshtastic community experimentation and private mesh networks.
