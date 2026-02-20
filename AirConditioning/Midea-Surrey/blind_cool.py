import asyncio
from msmart.device import AirConditioner as AC

import clima_utils

async def blind_cool():
    ac_cfg = clima_utils.get_ac_config()
    IP = ac_cfg["ip"]
    DEVICE_ID = ac_cfg["device_id"]
    try:
        device = AC(ip=IP, port=6444, device_id=DEVICE_ID)
        # NO REFRESH!
        device.power_state = True
        device.operational_mode = 2 # COOL
        device.target_temperature = 22.0
        device.fan_speed = 60
        device.eco = False
        device.turbo = False
        device.beep = True
        
        print("Sending blind apply (no refresh)...")
        await device.apply()
        print("Apply sent.")
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(blind_cool())
