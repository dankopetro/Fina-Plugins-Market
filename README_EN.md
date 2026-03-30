# 🌌 Fina Plugins Market: Universal Development Standards

To make a plugin compatible with Fina Ergen's "Zero-Config" interface, it must strictly follow this structure. This allows Fina to automatically locate the necessary scripts for the App buttons regardless of the user's hardware.

## 📂 Directory Structure

The Market repository is organized by **Category**, **Brand**, and **Model**. Fina will download the plugin and place it in `~/.config/Fina/plugins/`.

```text
[Category] / [Brand] / [Model] /
├── plugin.yaml          # Metadata and Voice Intents (MANDATORY)
├── README.md            # Plugin documentation
├── icon.png             # Optional: Icon to be displayed in the Market
└── (Automation .py scripts)
```

---

## 📋 Script Naming Convention

Fina's interface buttons execute scripts with specific names. If your plugin does not include these files, the corresponding button will show a "Script not found" error.

### 📺 Category: `TVs` and `Decos`
TV scripts must accept the `--ip` (mandatory) and `--mac` (in power scripts) arguments.

| Script | Button Action | Additional Arguments |
| :--- | :--- | :--- |
| `tv_power.py` | "Power" Button (On/Off toggle) | `--mac [MAC]` |
| `tv_input.py` | "TV/AIRE" Button (Switch to Antenna) | `--mac [MAC]` |
| `set_input_deco.py`| "HDMI" Button (Switch to Deco/HDMI) | |
| `tv_mute.py` | "Mute" Button | |
| `tv_volume_up.py` | "Vol +" Button | |
| `tv_volume_down.py`| "Vol -" Button | |
| `set_channel.py` | When clicking a channel in the list | `--channel [N]` |
| `list_tv_apps.py` | "Scan Apps" Button | |
| `launch_app.py` | When opening an App (YouTube, etc.) | `--package [NAME]` |
| `scan_ultra_fast.py`| "Ultra-fast Channel Scan" Button | |

### ❄️ Category: `AirConditioning`
Air conditioner control is centralized in a single master script named `clima.py`.

*   **Script:** `clima.py`
*   **Status Mode:** `--status` (Fina expects to read current temperature, mode, and power state).
*   **Control Mode:** `--temp [N]`, `--mode [cool/heat/dry/fan]`, `--power [on/off]`, `--turbo [on/off]`, `--swing [on/off]`.

### 🔔 Category: `Doorbells`
Security and video-doorbell control.

| Script | Purpose | Expected Output |
| :--- | :--- | :--- |
| `doorbell_status.py`| Battery Status | A simple number (e.g., `85`) |
| `monitor.py` | Start Quick View | `--trigger` argument |
| `hangup_doorbell.py`| End Communication | |

### 💡 Category: `Lights` and `SmartHome`
Smart lighting automation.

| Script | Action | Extra Argument |
| :--- | :--- | :--- |
| `light_on.py` | Turn on lights | |
| `light_off.py` | Turn off lights | |
| `set_brightness.py`| Change brightness | `--level [0-100]` |

### 🚪 Category: `Doors` and `Locks`
Automated doors and smart locks.

| Script | Action |
| :--- | :--- |
| `lock_on.py` | Lock door |
| `lock_off.py` | Unlock door |
| `lock_status.py` | Get lock status |

### 🪟 Category: `Blinds`
Smart blinds and curtain motors.

| Script | Action |
| :--- | :--- |
| `blinds_open.py` | Open blinds |
| `blinds_close.py` | Close blinds |
| `blinds_stop.py` | Stop moving |

### 🌱 Category: `Irrigation`
Smart watering and garden control.

| Script | Action |
| :--- | :--- |
| `watering_start.py`| Start watering cycle |
| `watering_stop.py` | Stop watering cycle |

### 🤖 Category: `Robots`
Vacuum and cleaning robots.

| Script | Action |
| :--- | :--- |
| `robot_clean.py` | Start cleaning |
| `robot_dock.py` | Return to base/dock |
| `robot_status.py`| Get battery/state |

### 🧊 Category: `Refrigerators` and `Appliances`
Smart fridges and heavy appliances.

| Script | Action |
| :--- | :--- |
| `fridge_status.py` | Read temp/general status |
| `fridge_inventory.py`| Read inventory (if supported) |

### ⚡ Category: `Energy`
Solar panel and inverter monitoring.

| Script | Action |
| :--- | :--- |
| `solar_status.py` | Read power production (W) |
| `battery_status.py` | Read home battery level |

---

## 📝 The `plugin.yaml` file

This is the most important file. It defines how Fina's AI interacts with your device.

```yaml
name: "Plugin Commercial Name"
version: "1.0.0"
author: "Your Name"
category: "TVs" # TVs, Decos, AirConditioning, Doorbells, Lights, Doors
model: "model_without_spaces" # Must match the final folder name

# INTENTS SYSTEM (Fina's Voice)
intents:
  - name: "intent_name"
    patterns: 
      - "activation phrase 1"
      - "activation phrase 2"
    action: "script_to_execute.py"
    response: "What Fina will say when executing it"
```

## 🛠️ Golden Rules for Developers

1.  **No IP Hardcoding**: Always use the `--ip` argument sent by Fina.
2.  **Relative Paths**: All scripts must be runnable from their own directory.
3.  **Standard Python**: Use standard libraries or include a `requirements.txt` if the plugin is complex.
4.  **Speed**: Fina is a fast control system. Optimize your scripts (ADB, HTTP, etc.) to respond in less than 2 seconds.

---
*Fina Ergen - Market Plugin Standards Documentation (2026)*
