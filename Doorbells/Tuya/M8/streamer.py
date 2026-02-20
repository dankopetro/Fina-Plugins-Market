#!/usr/bin/env python3
import http.server
import socketserver
import subprocess
import os
import time
import sys
import threading
import re

HTTP_PORT = 8555
WAYDROID_ADB = "192.168.240.112:5555"

def find_waydroid_ip():
    try:
        status_out = subprocess.getoutput("waydroid status")
        ip_match = re.search(r"IP address:\s+(192\.168\.\d+\.\d+)", status_out)
        if ip_match:
            return f"{ip_match.group(1)}:5555"
    except: pass
    return WAYDROID_ADB

# --- GLOBAL BUFFER ---
current_frame = None
frame_lock = threading.Lock()
capture_running = True
last_access = time.time()

def start_watchdog():
    print("⏲️ [Watchdog] Vigilante de inactividad iniciado (timeout: 180s)", flush=True)
    while True:
        waited = time.time() - last_access
        if waited > 180: # 3 minutos sin clientes
            print(f"💤 [Streamer] Inactivo por {int(waited)}s. Auto-destrucción para liberar RAM.", flush=True)
            # Intentar matar procesos hijos propios antes de morir
            os.system("pkill -P " + str(os.getpid()))
            os._exit(0)
        time.sleep(10)

def start_background_capture():
    global current_frame, WAYDROID_ADB
    print("🔁 [BgCapture] Iniciando captura continua...", flush=True)
    
    while capture_running:
        # 1. Asegurar IP
        WAYDROID_ADB = find_waydroid_ip()
        
        # 2. Comando Continuo
        cmd_stream = [
            "adb", "-s", WAYDROID_ADB, "exec-out", "screenrecord",
            "--output-format=h264", "--size", "320x576", "--bit-rate", "500000",
            "--time-limit", "180", "-"
        ]
        
        cmd_ffmpeg = [
            "ffmpeg", "-hide_banner", "-loglevel", "error",
            "-f", "h264", "-r", "10", "-i", "pipe:0", # Input: Forzar 10 FPS de lectura 
            "-an", "-c:v", "mjpeg", "-f", "mpjpeg", 
            "-r", "10", # Output: Forzar 10 FPS de salida
            "-boundary_tag", "frame", "-q:v", "20", "pipe:1" # Calidad q:v 20 (más ligera)
        ]

        try:
            adb_p = subprocess.Popen(cmd_stream, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            ffmpeg_p = subprocess.Popen(cmd_ffmpeg, stdin=adb_p.stdout, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            
            # Leer frames multiparte
            boundary = b'--frame\r\n'
            buffer = b''
            
            while True:
                chunk = ffmpeg_p.stdout.read(4096)
                if not chunk: break
                buffer += chunk
                
                # Buscar boundaries
                while True:
                    start = buffer.find(boundary)
                    if start == -1: break
                    
                    end = buffer.find(boundary, start + len(boundary))
                    if end == -1: break
                    
                    # Extraer frame completo (headers + jpeg)
                    part = buffer[start:end]
                    buffer = buffer[end:] # Avanzar buffer
                    
                    # Extraer solo el JPEG para guardar (saltar headers)
                    jpeg_start = part.find(b'\xff\xd8')
                    if jpeg_start != -1:
                        jpeg_data = part[jpeg_start:]
                        with frame_lock:
                            current_frame = jpeg_data
                            
        except Exception as e:
            print(f"⚠️ [BgCapture] Error: {e}. Reintentando en 2s...", flush=True)
            time.sleep(2)

class StreamingHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self, format, *args): return

    def do_GET(self):
        if self.path.startswith('/stream.mjpg'):
            self.send_response(200)
            self.send_header('Content-Type', 'multipart/x-mixed-replace; boundary=frame')
            self.send_header('Cache-Control', 'no-cache, no-store, must-revalidate')
            self.send_header('Connection', 'close')
            self.end_headers()
            
            print("🎥 [Streamer] Cliente conectado al flujo caliente.", flush=True)
            
            try:
                while True:
                    # Update local last_access to keep watchdog happy
                    global last_access
                    last_access = time.time()
                    
                    with frame_lock:
                        frame = current_frame
                    
                    if frame:
                        self.wfile.write(b"--frame\r\n")
                        self.wfile.write(b"Content-Type: image/jpeg\r\n")
                        self.wfile.write(f"Content-Length: {len(frame)}\r\n\r\n".encode())
                        self.wfile.write(frame)
                        self.wfile.write(b"\r\n")
                        self.wfile.flush()
                    
                    time.sleep(0.06) # ~15 FPS
            except:
                print("🔌 [Streamer] Cliente desconectado", flush=True)
                pass
                
        elif self.path.startswith('/view'):
            # ... (código existente view)
            self.send_response(200)
            self.send_header('Content-Type', 'text/html')
            self.end_headers()
            html = f"""
            <html><body style="margin:0;background:#000;display:flex;justify-content:center;height:100vh;">
            <img src="/stream.mjpg?t={time.time()}" style="max-height:100%;object-fit:contain;">
            </body></html>
            """
            self.wfile.write(html.encode())
        else:
            self.send_error(404)

    def _run_burst_mode(self): pass # Deprecated

class ThreadedServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True

if __name__ == "__main__":
    os.system("fuser -k 8555/tcp 2>/dev/null || true")
    
    # Arrancar captura en segundo plano
    t = threading.Thread(target=start_background_capture, daemon=True)
    t.start()
    
    # Arrancar watchdog de memoria
    threading.Thread(target=start_watchdog, daemon=True).start()
    
    print(f"📡 Servidor Video Híbrido V8 (Always-On) en puerto {HTTP_PORT}", flush=True)
    with ThreadedServer(('', HTTP_PORT), StreamingHandler) as server:
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
