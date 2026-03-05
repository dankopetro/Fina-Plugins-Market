# ❄️ Plugin Clima Master: Surrey / Midea

Este plugin permite a Fina Ergen controlar aires acondicionados inteligentes de las marcas **Midea** o **Surrey** que sean compatibles con la nube MideaSmart o conectividad IP local (como los módulos WiFi OSK103).

## 🚀 Funcionalidades Incluidas
*   **Gestión de Temperatura**: "Pon el aire a 24 grados", "Sube el aire".
*   **Modos de Enfriamiento/Calefacción**: "Pon el aire en Frío", "Pon el sire en Heat/Calor", "Modo ventilador".
*   **Potencia (Ventilador)**: "Pon el aire en modo turbo", "Baja la intensidad del aire", "Ventilador automático".
*   **Extras**: "Activa el movimiento del aire (Swing)", "Apaga el display del aire (Luz)".
*   **Encendido y Apagado**: "Prende el aire", "Apaga el split".

## 🛠️ Cómo Instalar este Plugin (Modo Manual)
Este plugin se puede instalar a través del **Fina Market** desde la interfaz de usuario. Si prefieres la instalación manual:

1.  Descarga este repositorio completo.
2.  Extrae la carpeta `AirConditioning/Midea-Surrey/`.
3.  Cópiala en la ruta de tu PC: `[Ruta-Fina-Ergen]/plugins/AirConditioning/Midea-Surrey/`.

## ⚙️ Dependencias
Este plugin utiliza módulos de python, instalalos ejecutando dentro de tu entorno virtual de conda o venv lo siguiente:
```bash
pip install msmart
```

## 🛠️ Configuración (Config local IP)
Para que el Asistente ubiqué el aire acondicionado, requiere saber su **IP fija** en tu red. Fina guarda esta configuración en su panel de "Ajustes", pero debajo del capó lo almacena en `user_settings.json`.

Si notas fallos al tratar de usarlo, comprueba que la IP de tu equipo o equipos Surrey/Midea no hayan cambiado (es recomendable reservar IPs estáticas desde tu router para aparatos Smart Home).
