# 📺 Plugin TCL / Android TV (tcl32s60a)

Este plugin añade capacidades de control total a tu asistente Fina Ergen para televisores inteligentes TCL y otros dispositivos basados en Android TV a través de la red (ADB).

## 🚀 Funcionalidades Incluidas
*   **Encendido y Apagado**: "Prende la tele", "Apaga el televisor".
*   **Control de Volumen**: "Sube el volumen", "Baja el volumen", "Mutea la tele".
*   **Gestión de Canales**: "Pon el canal 13", "Siguiente canal", "Canal anterior".
*   **Apertura de Aplicaciones**: "Abre YouTube", "Abre Netflix".

## 🛠️ Cómo Instalar este Plugin
Si no utilizas el instalador automático del "Fina Market" dentro de la aplicación, puedes instalar este plugin de forma manual:

1.  Descarga o clona este repositorio.
2.  Copia la carpeta `tcl32s60a` y colócala dentro de la carpeta `plugins/TVs/TCL/` en la ruta de instalación de tu Fina Ergen.
    *   *Ruta final esperada: `[Ruta-Fina-Ergen]/plugins/TVs/TCL/tcl32s60a/`*
3.  Asegúrate de tener **ADB** instalado (`sudo apt install adb`).
4.  Reinicia Fina Ergen.

## ⚙️ Requisitos Previos en el Televisor
Para que este plugin funcione, necesitas activar la **"Depuración por USB"** o **"Depuración Inalámbrica"** en los ajustes de desarrollador de tu TV.
1.  Ve a los ajustes de tu TV > Preferencias del dispositivo > Acerca de.
2.  Pulsa 7 veces sobre el número de "Compilación".
3.  Vuelve atrás y entra en las "Opciones de Desarrollador".
4.  Activa "Depuración de red" o "Depuración de red por ADB".

> **Nota**: Durante el primer uso, es posible que el televisor muestre un mensaje en pantalla preguntando si autorizas a tu PC a conectarse. Debes marcar la opción **"Permitir siempre desde esta computadora"**.
