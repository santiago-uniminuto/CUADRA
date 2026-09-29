# Gunicorn (servidor WSGI). Ejecutar desde la raíz del proyecto:
#   gunicorn config.wsgi:application -c deploy/gunicorn.conf.py
# Requiere Linux/macOS/WSL2 (Gunicorn no corre en Windows nativo).
bind = "127.0.0.1:8000"   # Nginx hace de proxy inverso hacia este puerto
workers = 3
timeout = 30
