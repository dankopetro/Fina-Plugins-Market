
import os
import subprocess
import time

WAYDROID_ADB = "192.168.240.112:5555"

def check_packages():
    print("🔌 Conectando ADB...")
    subprocess.run(f"adb connect {WAYDROID_ADB}", shell=True)
    time.sleep(2)
    
    print("🔍 Buscando paquetes 'tuya'...")
    try:
        res = subprocess.check_output(f"adb -s {WAYDROID_ADB} shell pm list packages | grep tuya", shell=True).decode()
        if res:
            print("📦 PAQUETES ENCONTRADOS:")
            print(res)
        else:
            print("⚠️ No se encontraron paquetes con 'tuya' en el nombre.")
    except Exception as e:
        print(f"❌ Error al listar paquetes: {e}")
        # Intentar listar ALL packages y grepear localmente por si acaso
        try:
             res = subprocess.check_output(f"adb -s {WAYDROID_ADB} shell pm list packages", shell=True).decode()
             found = [line for line in res.splitlines() if "tuya" in line.lower()]
             if found:
                 print("📦 PAQUETES ENCONTRADOS (Grep local):")
                 for f in found: print(f)
             else:
                 print("⚠️ Nada encontrado.")
        except: pass

if __name__ == "__main__":
    check_packages()
