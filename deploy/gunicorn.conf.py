"""Configuration gunicorn pour EVE Pilot.

Bind sur 127.0.0.1:8001 (boucle locale uniquement) : le reverse proxy
(Apache/nginx, geré par ISPConfig) y accede, gunicorn n'est jamais expose
directement a internet. Choix TCP plutot que socket Unix pour eviter les
problemes de permissions entre l'utilisateur gunicorn et www-data sous
ISPConfig.
"""

import multiprocessing

bind = "127.0.0.1:8001"
# Regle empirique : (2 x coeurs) + 1, plafonne pour un petit VPS.
workers = min((multiprocessing.cpu_count() * 2) + 1, 5)
worker_class = "sync"
timeout = 60
graceful_timeout = 30
keepalive = 5
# Recycle les workers pour limiter les fuites memoire.
max_requests = 1000
max_requests_jitter = 100
# Logs vers stdout/stderr -> captures par systemd/journald.
accesslog = "-"
errorlog = "-"
loglevel = "info"
