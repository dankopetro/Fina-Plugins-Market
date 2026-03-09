#!/usr/bin/env python3
import http.server
import socketserver
import subprocess
import os
import time
import sys
import threading
import re
from typing import Optional, Any, List, Dict, Tuple, cast

HTTP_PORT: int = 8555
WAYDROID_ADB_DEFAULT: str = "127.0.0.1:5555"

def get_waydroid_ip() -> str:
    """Intenta detectar la IP de Waydroid dinámicamente"""
    try:
        # Usamos check_output para capturar salida de forma segura
        status_out: str = subprocess.check_output(["waydroid", "status"], text=True, timeout=5) # type: ignore
        # Regex más permisiva para cualquier IP privada
        ip_match = re.search(r"IP address:\s+((?:192\.168|172\.[1-3][0-9]|10)\.\d+\.\d+\.\d+)", status_out)
        if ip_match:
            return f"{ip_match.group(1)}:5555"
    except Exception:
        pass
    return WAYDROID_ADB_DEFAULT

# --- BUFFER GLOBAL DE VIDEO ---
_current_frame: Optional[bytes] = None
_frame_lock: threading.Lock = threading.Lock()
_capture_active: bool = True
_last_request_time: float = time.time()

def watchdog_routine() -> None:
    """Monitorea inactividad para liberar recursos del sistema"""
    print("⏲️ [Watchdog] Vigilante de recursos activo.")
    while True:
        inactive_seconds: float = time.time() - _last_request_time
        if inactive_seconds > 1800: # 30 min sin clientes
            print(f"💤 [Streamer] Inactivo por {int(inactive_seconds)}s. Liberando servicios.")
            # Matar procesos hijos (ffmpeg/adb)
            subprocess.run(["pkill", "-P", str(os.getpid())], capture_output=True) # type: ignore
            os._exit(0)
        time.sleep(30)

def capture_worker() -> None:
    """Captura continua de pantalla Android vía ADB + FFMPEG"""
    global _current_frame
    print("🔁 [Capture] Iniciando motor de video MJPEG...")
    
    while _capture_active:
        target_adb: str = get_waydroid_ip()
        
        # ADB screenrecord a pipe
        cmd_adb: List[str] = [
            "adb", "-s", target_adb, "exec-out", "screenrecord",
            "--output-format=h264", "--size", "320x576", "--bit-rate", "500000",
            "--time-limit", "180", "-"
        ]
        
        # FFMPEG a MJPEG
        cmd_ffmpeg: List[str] = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "h264", "-r", "10", "-i", "pipe:0",
            "-an", "-c:v", "mjpeg", "-f", "mpjpeg", 
            "-r", "10", "-boundary_tag", "frame", "-q:v", "20", "pipe:1"
        ]

        adb_p: Any = None 
        ffmpeg_p: Any = None 

        try:
            adb_p = subprocess.Popen(cmd_adb, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if adb_p.stdout is None:
                continue
                
            ffmpeg_p = subprocess.Popen(cmd_ffmpeg, stdin=adb_p.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            if ffmpeg_p.stdout is None:
                continue
            
            boundary: bytes = b'--frame\r\n'
            buffer: bytearray = bytearray() # type: ignore
            
            while _capture_active:
                chunk: bytes = ffmpeg_p.stdout.read(8192) # type: ignore
                if not chunk: break
                
                buffer.extend(chunk)
                
                while True:
                    start: int = buffer.find(boundary)
                    if start == -1: break
                    
                    next_pos: int = buffer.find(boundary, start + len(boundary))
                    if next_pos == -1: break
                    
                    part: bytes = bytes(buffer[start:next_pos]) # type: ignore
                    del buffer[:next_pos] # type: ignore
                    
                    # Extraer JPEG
                    jpeg_start: int = part.find(b'\xff\xd8')
                    if jpeg_start != -1:
                        with _frame_lock:
                            _current_frame = part[jpeg_start:] # type: ignore
        except Exception as e:
            print(f"⚠️ [Capture] Error de flujo: {e}")
        finally:
            if ffmpeg_p: ffmpeg_p.terminate()
            if adb_p: adb_p.terminate()
        
        time.sleep(2)

class StreamingHandler(http.server.BaseHTTPRequestHandler):
    """Manejador HTTP para entrega MJPEG"""
    def log_message(self, format: str, *args: Any) -> None:
        """Silenciar logs HTTP estándar"""
        pass

    def do_GET(self) -> None:
        """Ruta de video stream"""
        global _last_request_time
        _last_request_time = time.time()

        if self.path.startswith('/stream.mjpg'):
            try:
                self.send_response(200)
                self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
                self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
                self.send_header('Connection', 'close')
                self.end_headers()
                
                while True:
                    with _frame_lock:
                        frame: Optional[bytes] = _current_frame
                    
                    if frame:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    
                    time.sleep(0.06) # ~16 FPS
            except Exception:
                print("🔌 [Streamer] Cliente desconectado", flush=True)
                
        elif self.path.startswith('/view'):
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html: str = f"""
            <html><body style="margin:0;background:#000;display:flex;justify-content:center;height:100vh;">
            <img src="/stream.mjpg?t={time.time()}" style="max-height:100%;object-fit:contain;">
            </body></html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    """Servidor TCP multi-hilo"""
    allow_reuse_address = True
    daemon_threads = True

def main() -> None:
    """Arranque del servidor de video"""
    # Limpiar puertos previos
    subprocess.run(["fuser", "-k", f"{HTTP_PORT}/tcp"], capture_output=True) # type: ignore
    
    # Hilos de soporte
    threading.Thread(target=capture_worker, daemon=True).start()
    threading.Thread(target=watchdog_routine, daemon=True).start()
    
    print(f"📡 Video Streamer Ergen activo en puerto {HTTP_PORT}")
    with ThreadedServer(('', HTTP_PORT), StreamingHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("⏹ Deteniendo servidor.")
        except Exception as e:
            print(f"💥 Error fatal: {e}")
            sys.exit(1)

if __name__ == "__main__":
    main()
