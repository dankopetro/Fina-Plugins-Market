# 📹 Cambios para la Visualización de Video en Fina

## 📅 Fecha: 25/01/2025

## 🔄 Cambios Realizados

### 1. Estructura del Sistema de Streaming

- **Streamer de Video** (`streamer.py`):
  - Captura la pantalla de Waydroid usando `scrcpy`
  - Sirve un stream MJPEG en `http://localhost:8555/stream.mjpg`
  - Resolución: 360x640 a 2 FPS
  - Se ejecuta como un proceso independiente

- **Monitor** (`monitor.py`):
  - Se asegura de que el streamer esté siempre activo
  - Verifica el estado de Waydroid y ADB
  - Reintenta automáticamente si hay fallos

### 2. Integración Frontend (Vue.js)

- **App.vue**:
  - Botón "Probar Timbre (Manual)" para pruebas
  - Iframe que muestra el stream MJPEG
  - Refresco automático cada 30 segundos
  - Manejo de errores mejorado

- **Lógica de Inicio del Stream**:
  - Se puede iniciar manualmente desde el botón
  - O automáticamente al detectar el timbre

## ⚙️ Configuración Automática

### Requisitos Previos

1. Asegurarse de que `monitor.py` se ejecute al inicio de Fina
2. Verificar que Waydroid esté correctamente instalado y configurado
3. Tener permisos ADB configurados para el usuario

### Pasos para la Configuración Automática

1. **Inicio Automático del Monitor**:
   Asegurarse de que `monitor.py` se ejecute al iniciar Fina. Esto se puede hacer desde el script de inicio principal de la aplicación.

2. **Configuración de Waydroid**:
   ```bash
   # Verificar que Waydroid esté corriendo
   waydroid status
   
   # Si no está corriendo, iniciarlo
   waydroid session start
   ```

3. **Permisos ADB**:
   ```bash
   # Verificar que el dispositivo esté conectado
   adb devices
   
   # Si no aparece, reiniciar el servidor ADB
   adb kill-server
   adb start-server
   ```

4. **Prueba del Streamer**:
   - Iniciar Fina
   - Verificar que `monitor.py` esté en ejecución
   - Abrir `http://localhost:8555/view` en un navegador
   - El video debería aparecer automáticamente

## 🔍 Solución de Problemas Comunes

### El video no aparece
1. Verificar que `monitor.py` esté en ejecución
2. Revisar los logs en la consola de Fina
3. Probar manualmente: `python3 streamer.py`

### Error de ADB
1. Verificar conexión ADB: `adb devices`
2. Reiniciar ADB: `adb kill-server && adb start-server`
3. Reiniciar Waydroid si es necesario

### El video se congela
- El iframe se refresca automáticamente cada 30 segundos
- Si persiste, verificar la conexión de red y recursos del sistema

## 📝 Notas Adicionales

- El streamer está configurado para usar pocos recursos (2 FPS, resolución baja)
- Los logs detallados están disponibles en la consola de Fina
- Para mayor rendimiento, cerrar aplicaciones que no sean necesarias

## 🔄 Proceso de Inicio

1. Fina inicia
2. `monitor.py` se ejecuta automáticamente
3. El monitor verifica Waydroid y ADB
4. Si todo está bien, inicia `streamer.py`
5. La interfaz de usuario muestra el botón de prueba
6. Al presionar el botón, se muestra el iframe con el stream

## 📋 Estado Actual

- [x] Streamer funcional
- [x] Integración con interfaz de usuario
- [x] Refresco automático
- [x] Manejo de errores básico
- [ ] Pruebas en diferentes dispositivos
- [ ] Optimización de rendimiento

## 👨‍💻 Soporte

Para problemas adicionales, contactar al equipo de desarrollo o revisar los logs en:
- Consola de Fina
- Logs de sistema
- Salida de `journalctl` para servicios relacionados
