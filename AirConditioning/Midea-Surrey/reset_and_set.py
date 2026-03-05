import asyncio
from msmart.device import AirConditioner as AC

import clima_utils

async def reset_and_set():
    ac_cfg = clima_utils.get_ac_config()
    IP = ac_cfg["ip"]
    DEVICE_ID = ac_cfg["device_id"]
    try:
        device = AC(ip=IP, port=6444, device_id=DEVICE_ID)
        await device.refresh()
        print("Initial Mode:", device.operational_mode)
        
        print("Turning OFF...")
        device.power_state = False
        await device.apply()
        await asyncio.sleep(2)
        
        print("Turning ON in COOL mode...")
        device.power_state = True
        device.operational_mode = 2 # COOL
        await device.apply()
        
        await asyncio.sleep(2)
        await device.refresh()
        print("Final Mode:", device.operational_mode)
        
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(reset_and_set())
