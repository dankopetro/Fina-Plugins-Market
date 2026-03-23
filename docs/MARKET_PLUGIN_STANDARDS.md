# 🌌 Fina Plugins Market: Estándares de Desarrollo Universal

Para que un plugin sea compatible con la interfaz "Zero-Config" de Fina Ergen, debe seguir esta estructura estrictamente. Esto permite que Fina localice automáticamente los scripts necesarios para los botones de la App sin importar el hardware del usuario.

## 📂 Estructura de Directorios

El repositorio del Market se organiza por **Categoría**, **Marca** y **Modelo**. Fina descargará el plugin y lo ubicará en `~/.config/Fina/plugins/`.

```text
[Categoría] / [Marca] / [Modelo] /
├── plugin.yaml          # Metadatos e Intents de voz (OBLIGATORIO)
├── README.md            # Documentación del plugin
├── icon.png             # OIcono que se verá en el Market
└── (Scripts de automatización .py)
```

---

## 📋 Convención de Nombres de Scripts

Los botones de la interfaz de Fina ejecutan scripts con nombres específicos. Si tu plugin no incluye estos archivos, el botón correspondiente mostrará un error de "Script no encontrado".

### 📺 Categoría: `TVs` y `Decos`
Los scripts de TV deben aceptar el argumento `--ip` (obligatorio) y `--mac` (en scripts de encendido).

| Script | Acción del Botón | Argumentos adicionales |
| :--- | :--- | :--- |
| `tv_power.py` | Botón "Power" (On/Off toggle) | `--mac [MAC]` |
| `tv_input.py` | Botón "TV/AIRE" (Cambio a antena) | `--mac [MAC]` |
| `set_input_deco.py`| Botón "HDMI" (Cambio al deco) | |
| `tv_mute.py` | Botón "Mute" | |
| `tv_volume_up.py` | Botón "Vol +" | |
| `tv_volume_down.py`| Botón "Vol -" | |
| `set_channel.py` | Al pulsar un canal de la lista | `--channel [N]` |
| `list_tv_apps.py` | Botón "Escanear Apps" | |
| `launch_app.py` | Al abrir una App (YouTube, etc) | `--package [NAME]` |
| `scan_ultra_fast.py`| Botón "Escaneo Rápido de Canales"| |

### ❄️ Categoría: `AirConditioning`
El control del aire se centraliza en un único script maestro llamado `clima.py`.

*   **Script:** `clima.py`
*   **Modo Status:** `--status` (Fina espera leer temperatura actual, modo y estado de energía).
*   **Modo Control:** `--temp [N]`, `--mode [cool/heat/dry/fan]`, `--power [on/off]`, `--turbo [on/off]`, `--swing [on/off]`.

### 🔔 Categoría: `Doorbells`
Control de seguridad y video-porteros.

| Script | Propósito | Salida esperada |
| :--- | :--- | :--- |
| `doorbell_status.py`| Estado de batería | Un número (Ej: `85`) |
| `monitor.py` | Iniciar visualización rápida | Argumento `--trigger` |
| `hangup_doorbell.py`| Cerrar comunicación | |

### 💡 Categoría: `Lights` y `SmartHome`
Control de iluminación y enchufes inteligentes.

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `lights_on.py` | Encender todas las luces | |
| `lights_off.py` | Apagar todas las luces | |
| `set_brightness.py` | Ajustar nivel de brillo | `--level [0-100]` |
| `set_color.py` | Cambiar color (RGB/Hex) | `--hex [#FFFFFF]` |

### 🧹 Categoría: `Robots`
Aspiradoras y robots de limpieza (Roomba, Roborock, etc).

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `robot_clean.py` | Iniciar limpieza completa | |
| `robot_stop.py` | Detener y volver a base | |
| `robot_status.py` | Estado de batería y depósito| |

### 🔒 Categoría: `Locks`
Cerraduras inteligentes (Nuki, August, etc).

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `lock_door.py` | Cerrar con llave | |
| `unlock_door.py` | Abrir cerradura | |
| `lock_status.py` | Saber si está bloqueada | |

### 💧 Categoría: `Irrigation` y `Blinds`
Zonas de riego y persianas/cortinas.

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `irrigation_on.py` | Iniciar riego | `--zone [1-9]` |
| `irrigation_off.py`| Detener riego | |
| `blinds_open.py` | Abrir persianas | `--level [0-100]` |
| `blinds_close.py` | Cerrar persianas | |

### ⚡ Categoría: `Energy`
Inversores solares y cargadores de vehículos eléctricos (Tesla, Wallbox, Fronius).

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `power_status.py` | Producción solar actual | |
| `battery_status.py`| Carga de batería/auto | |
| `start_charge.py` | Iniciar carga EV | |

### 🧺 Categoría: `Appliances`
Lavarropas, heladeras y hornos inteligentes (Samsung, LG, Haier).

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `appliance_start.py`| Iniciar ciclo (lavado/etc)| `--mode [normal/fast]`|
| `appliance_status.py`| Tiempo restante/estado | |

### 🧊 Categoría: `Refrigerators`
Heladeras y congeladores inteligentes.

| Script | Acción | Argumentos |
| :--- | :--- | :--- |
| `fridge_status.py` | Temperatura actual y modo | |
| `set_fridge_temp.py`| Ajustar temperatura | `--temp [N]` |
| `fridge_inventory.py`| Lista de ítems faltantes | |

---

## 📝 El archivo `plugin.yaml`

Es el archivo más importante. Define cómo interactúa la IA de Fina con tu dispositivo.

```yaml
name: "Nombre comercial del Plugin"
version: "1.0.0"
author: "Tu Nombre"
category: "TVs" # TVs, Decos, AirConditioning, Doorbells, Lights, Doors
model: "modelo_sin_espacios" # Debe coincidir con el nombre de la carpeta final

# SISTEMA DE INTENTS (Voz de Fina)
intents:
  - name: "nombre_del_intent"
    patterns: 
      - "frase de activación 1"
      - "frase de activación 2"
    action: "script_a_ejecutar.py"
    response: "Lo que Fina dirá al ejecutarlo"
```

## 🛠️ Reglas de Oro para Desarrolladores

1.  **Sin Hardcoding de IPs**: Siempre usa el argumento `--ip` que Fina envía al script.
2.  **Rutas Relativas**: Todos los scripts deben poder ejecutarse desde su propia carpeta.
3.  **Python Estándar**: Usa librerías estándar o incluye un `requirements.txt` si el plugin es complejo.
4.  **Velocidad**: Fina es un sistema de control rápido. Optimiza tus scripts (ADB, HTTP, etc.) para que respondan en menos de 2 segundos.

---
*Fina Ergen - Documentación de Estándares para el Market (2026)*
