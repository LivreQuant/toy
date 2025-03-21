# health_server.py
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading
import logging
import os
import psutil

logger = logging.getLogger('health_server')

class HealthHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/health' or self.path == '/healthz':
            # Basic health check
            self.send_response(200)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'OK')
        elif self.path == '/readiness':
            # More detailed readiness check
            try:
                # Check memory usage
                memory = psutil.virtual_memory()
                memory_ok = memory.percent < 90  # Less than 90% memory use
                
                # Check CPU usage
                cpu_ok = psutil.cpu_percent(interval=0.1) < 95  # Less than 95% CPU use
                
                if memory_ok and cpu_ok:
                    self.send_response(200)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'READY')
                else:
                    self.send_response(503)
                    self.send_header('Content-type', 'text/plain')
                    self.end_headers()
                    self.wfile.write(b'NOT READY - Resource constraints')
            except Exception as e:
                logger.error(f"Error in readiness check: {e}")
                self.send_response(500)
                self.send_header('Content-type', 'text/plain')
                self.end_headers()
                self.wfile.write(f"Error in readiness check: {str(e)}".encode())
        else:
            self.send_response(404)
            self.send_header('Content-type', 'text/plain')
            self.end_headers()
            self.wfile.write(b'Not Found')
    
    def log_message(self, format, *args):
        # Suppress logs for health checks to avoid noise, except for errors
        if args[1] not in ['200', '204']:
            logger.warning(format % args)

def start_health_server():
    """Start health check HTTP server in a background thread"""
    port = int(os.getenv('HEALTH_PORT', '8088'))
    
    def run_server():
        server = HTTPServer(('0.0.0.0', port), HealthHandler)
        logger.info(f"Health check server started on port {port}")
        server.serve_forever()
    
    thread = threading.Thread(target=run_server, daemon=True)
    thread.start()
    return thread