import tinytuya
import json
import sys
import os

def get_battery():
    # Intentar localizar tuya_config.json en la nueva estructura ~/.config/Fina
    script_dir = os.path.dirname(os.path.abspath(__file__))
    def get_config_dir():
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return os.path.join(xdg_config, "Fina")
        return os.path.expanduser("~/.config/Fina")

    config_dir = get_config_dir()
    config_path = os.path.join(config_dir, "tuya_config.json")
    
    if not os.path.exists(config_path):
        # Fallback a la ruta antigua o relativa
        config_path = os.path.join(script_dir, "../../config/tuya_config.json")
        if not os.path.exists(config_path):
            config_path = "./config/tuya_config.json"
        if not os.path.exists(config_path):
            return "N/A"
        
    try:
        with open(config_path, "r") as f:
            config = json.load(f)

        c = tinytuya.Cloud(
            apiRegion=config['region_code'],
            apiKey=config['access_id'],
            apiSecret=config['access_secret'],
            uid=config['uid']
        )

        status = c.getstatus(config['device_id'])
        if status.get('success'):
            for dp in status.get('result', []):
                if dp.get('code') == 'wireless_electricity':
                    return str(dp.get('value'))
        return "N/A"
    except:
        return "N/A"

if __name__ == "__main__":
    print(get_battery())
