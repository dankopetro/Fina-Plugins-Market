import os
import json

def get_ac_config():
    """Carga la configuración del Aire Acondicionado desde settings.json"""
    # Defaults
    config = {
        "ip": "192.168.0.213",
        "device_id": 30786325625801
    }
    
    try:
        script_dir = os.path.dirname(os.path.abspath(__file__))
        # Intentar localizar settings.json (ruta relativa al plugin y nueva estructura)
        def get_config_dir():
            xdg_config = os.environ.get("XDG_CONFIG_HOME")
            if xdg_config:
                return os.path.join(xdg_config, "Fina")
            return os.path.expanduser("~/.config/Fina")

        config_dir = get_config_dir()
        paths = [
            os.path.join(config_dir, "settings.json"),
            os.path.join(script_dir, "../../config/settings.json"),
            os.path.join(script_dir, "../config/settings.json"),
            "./config/settings.json"
        ]
        
        for p in paths:
            if os.path.exists(p):
                with open(p, "r") as f:
                    data = json.load(f)
                    apis = data.get("apis", {})
                    config["ip"] = apis.get("AC_IP", config["ip"])
                    config["device_id"] = apis.get("AC_DEVICE_ID", config["device_id"])
                    break
    except:
        pass
        
    return config
