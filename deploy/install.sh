#!/usr/bin/env bash
#
# Installation EVE Pilot sur le VPS (côté système : PostgreSQL, venv, deps,
# migrations, fichiers statiques, service gunicorn). À lancer EN root/sudo.
#
# NE touche PAS à ISPConfig, Apache/nginx, ni au mail : ces points se règlent
# dans l'interface ISPConfig (créer le site + SSL Let's Encrypt + directive
# reverse-proxy vers 127.0.0.1:8001). Cf. docs/DEPLOIEMENT_VPS.md section ⭐.
#
# Idempotent : peut être relancé sans casse.
#
# Usage :
#   sudo APP_DIR=/srv/eve_pilot \
#        PG_PASSWORD='motdepasse_fort' \
#        DOMAIN=pilot.eve-sn.org \
#        bash deploy/install.sh
#
set -euo pipefail

APP_DIR="${APP_DIR:-/srv/eve_pilot}"
APP_USER="${APP_USER:-eve}"
PG_DB="${PG_DB:-eve_pilot}"
PG_USER="${PG_USER:-eve_pilot}"
PG_PASSWORD="${PG_PASSWORD:-}"
DOMAIN="${DOMAIN:-pilot.eve-sn.org}"

log() { echo -e "\n=== $* ==="; }

if [[ $EUID -ne 0 ]]; then echo "À lancer en root (sudo)."; exit 1; fi
if [[ -z "$PG_PASSWORD" ]]; then echo "PG_PASSWORD est requis (mot de passe PostgreSQL)."; exit 1; fi
if [[ ! -f "$APP_DIR/manage.py" ]]; then
  echo "Code introuvable dans $APP_DIR (manage.py absent)."
  echo "Transférer le projet dans $APP_DIR (git clone / scp) puis relancer."
  exit 1
fi

# Garde-fou : le port gunicorn (8001) ne doit pas déjà être pris par un autre
# service (on est sur un serveur de prod partagé : mail/web/DNS).
if ss -ltn 2>/dev/null | grep -q ':8001 '; then
  echo "⚠️  Le port 8001 est déjà utilisé. Choisir un autre port :"
  echo "    - éditer 'bind' dans deploy/gunicorn.conf.py,"
  echo "    - et la directive reverse-proxy ISPConfig en conséquence."
  exit 1
fi

log "1. Paquets système (PostgreSQL, venv, git) — n'installe PAS de serveur web"
apt-get update -y
apt-get install -y python3 python3-venv python3-pip postgresql git

log "2. Utilisateur applicatif $APP_USER"
if ! id "$APP_USER" &>/dev/null; then
  adduser --system --group --home "$APP_DIR" "$APP_USER"
fi
chown -R "$APP_USER:$APP_USER" "$APP_DIR"

log "3. Base PostgreSQL ($PG_DB / $PG_USER) — idempotent"
sudo -u postgres psql -v ON_ERROR_STOP=1 <<SQL
DO \$\$ BEGIN
  IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = '$PG_USER') THEN
    CREATE ROLE $PG_USER LOGIN PASSWORD '$PG_PASSWORD';
  ELSE
    ALTER ROLE $PG_USER PASSWORD '$PG_PASSWORD';
  END IF;
END \$\$;
SELECT 'CREATE DATABASE $PG_DB OWNER $PG_USER'
  WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = '$PG_DB')\gexec
ALTER ROLE $PG_USER SET client_encoding TO 'utf8';
ALTER ROLE $PG_USER SET timezone TO 'Africa/Dakar';
SQL

log "4. Environnement Python (.venv) + dépendances"
sudo -u "$APP_USER" python3 -m venv "$APP_DIR/.venv"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install --upgrade pip
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/pip" install -r "$APP_DIR/requirements.txt"

log "5. Fichier .env (créé depuis le modèle si absent)"
ENV_FILE="$APP_DIR/.env"
if [[ ! -f "$ENV_FILE" ]]; then
  cp "$APP_DIR/.env.production.example" "$ENV_FILE"
  SECRET="$("$APP_DIR/.venv/bin/python" -c 'import secrets; print(secrets.token_urlsafe(64))')"
  sed -i "s|^DJANGO_SECRET_KEY=.*|DJANGO_SECRET_KEY=$SECRET|" "$ENV_FILE"
  sed -i "s|^DJANGO_ALLOWED_HOSTS=.*|DJANGO_ALLOWED_HOSTS=$DOMAIN|" "$ENV_FILE"
  sed -i "s|^DJANGO_CSRF_TRUSTED_ORIGINS=.*|DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMAIN|" "$ENV_FILE"
  sed -i "s|^POSTGRES_DB=.*|POSTGRES_DB=$PG_DB|" "$ENV_FILE"
  sed -i "s|^POSTGRES_USER=.*|POSTGRES_USER=$PG_USER|" "$ENV_FILE"
  sed -i "s|^POSTGRES_PASSWORD=.*|POSTGRES_PASSWORD=$PG_PASSWORD|" "$ENV_FILE"
  sed -i "s|^SITE_BASE_URL=.*|SITE_BASE_URL=https://$DOMAIN|" "$ENV_FILE"
  echo "  .env généré. ⚠️ Compléter EMAIL_HOST_PASSWORD à la main."
else
  echo "  .env déjà présent : laissé tel quel."
fi
chown "$APP_USER:$APP_USER" "$ENV_FILE"
chmod 600 "$ENV_FILE"

log "6. Migrations + fichiers statiques"
cd "$APP_DIR"
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" manage.py migrate --noinput
sudo -u "$APP_USER" "$APP_DIR/.venv/bin/python" manage.py collectstatic --noinput

log "7. Service systemd gunicorn (127.0.0.1:8001)"
cp "$APP_DIR/deploy/eve_pilot.service" /etc/systemd/system/eve_pilot.service
systemctl daemon-reload
systemctl enable --now eve_pilot
sleep 2
systemctl --no-pager --full status eve_pilot | head -n 12 || true

cat <<NEXT

============================================================
✅ Côté système : terminé.

Vérif rapide :  curl -s http://127.0.0.1:8001/health/   (doit répondre, via Host autorisé)
  -> si "Bad Request (400)", c'est normal en direct : ALLOWED_HOSTS=$DOMAIN.
     Le test réel se fait via https://$DOMAIN/health/ une fois ISPConfig branché.

Il reste 3 actions MANUELLES (hors de ce script) :
  1. DNS chez LWS : enregistrement A  $DOMAIN  ->  IP publique du VPS.
  2. ISPConfig : créer le site $DOMAIN, cocher SSL + Let's Encrypt, PHP désactivé.
  3. ISPConfig : coller la directive reverse-proxy (Apache ou nginx) vers
     http://127.0.0.1:8001  (voir docs/DEPLOIEMENT_VPS.md section ⭐ C).

Créer un compte admin :  sudo -u $APP_USER $APP_DIR/.venv/bin/python $APP_DIR/manage.py createsuperuser
============================================================
NEXT
