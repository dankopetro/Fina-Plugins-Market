import asyncio
from msmart.device import AirConditioner as AC

import clima_utils

async def sweep_modes():
    ac_cfg = clima_utils.get_ac_config()
    IP = ac_cfg["ip"]
    DEVICE_ID = ac_cfg["device_id"]
    try:
        device = AC(ip=IP, port=6444, device_id=DEVICE_ID)
        await device.refresh()
        
        mode_names = {1: "Auto", 2: "Cool", 3: "Dry", 4: "Heat", 5: "Fan"}
        
        for m in range(1, 6):
            print(f"\n--- Probando Modo {m} ({mode_names[m]}) ---")
            device.power_state = True
            device.operational_mode = m
            await device.apply()
            await asyncio.sleep(2)
            await device.refresh()
            print(f"Estado real despues de setear {m}: {device.operational_mode} ({mode_names.get(device.operational_mode, '???')})")
            
    except Exception as e:
        print("Error:", e)

if __name__ == "__main__":
    asyncio.run(sweep_modes())
