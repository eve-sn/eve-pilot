# Déploiement EVE Pilot sur VPS (test en ligne)

> Cible : VPS **Linux Ubuntu/Debian**, application accessible sur **https://pilot.eve-sn.org** pour les collègues de Pikine, Saint-Louis et Kédougou.
> Pile : **gunicorn** (app) → **nginx** (reverse proxy + TLS) → **PostgreSQL**. TLS gratuit via **Let's Encrypt**.
> Remplacer `pilot.eve-sn.org` par le sous-domaine choisi, partout.

⚠️ **Données sensibles.** L'app contient salaires, n° CNI/IPRES/CSS, pièces financières. Ce déploiement applique : HTTPS obligatoire, `DEBUG=False`, médias servis **uniquement après login**, cookies sécurisés, pare-feu. **Pour ce premier test public, privilégier des données fictives** ; ne charger la paie réelle qu'une fois l'accès validé.

---

## ⭐ VOTRE CAS : VPS sous ISPConfig + DNS chez LWS

Le VPS `serveur-vps.net` (**IP publique : `91.234.194.71`**) tourne **ISPConfig** et héberge **déjà en production le site eve-sn.org + les mails professionnels + le DNS**. On **n'installe donc PAS** nginx/certbot à la main (étape 8) — on s'intègre à ISPConfig. Le reste (PostgreSQL, code, venv, `.env`, migrate, gunicorn systemd) reste valable.

> 🛡️ **Cohabitation avec la prod existante (site + mail).** On **ajoute un site** (`pilot.eve-sn.org`), on ne crée PAS de nouveau serveur. C'est isolé du site eve-sn.org et du mail. **Deux précautions impératives :**
> 1. **Prendre un SNAPSHOT du VPS** avant de commencer (interface serveur-vps.net) → rollback en 1 clic si besoin.
> 2. **NE PAS toucher au pare-feu** (étape 9 ignorée) : ce serveur fait mail+DNS+web ; un `ufw enable` mal réglé couperait mails/DNS/SSH. Il a déjà ses règles.
> Et **ne pas faire d'`apt upgrade` global** : seulement installer les paquets nécessaires (le script `install.sh` le fait déjà ainsi).

### A. DNS (chez LWS) — à corriger d'abord
Tu as créé `pilot.eve-sn.org` en « sous-domaine → répertoire », ce qui pointe vers l'hébergement **LWS**, pas vers le VPS. Il faut à la place un **enregistrement A** :
- Dans le panel LWS, **zone DNS** d'`eve-sn.org` : créer `pilot` **type A** → **`91.234.194.71`**. Supprimer le « sous-domaine répertoire » LWS s'il crée un conflit.
- Vérifier : `dig +short pilot.eve-sn.org` doit renvoyer `91.234.194.71`.

### B. Créer le site dans ISPConfig
1. **Sites → Site web → Ajouter** : domaine `pilot.eve-sn.org`, client = EVE.
2. Cocher **SSL** et **Let's Encrypt** (ISPConfig génère le certificat automatiquement une fois le DNS propagé).
3. Laisser **PHP = Désactivé** (l'app est en Python, pas PHP).

### C. Brancher le site sur gunicorn (reverse proxy)
gunicorn tourne en local sur le socket `/run/eve_pilot.sock` (étape 7). On ajoute une directive dans le site ISPConfig. **WhiteNoise sert le `/static/` et Django sert `/media/` (protégé)** : on proxifie donc simplement tout vers gunicorn.

**Apache (VOTRE cas)** — Onglet *Options* du site → champ *Directives Apache*. Activer d'abord les modules : `sudo a2enmod proxy proxy_http headers && sudo systemctl reload apache2`.
```apache
ProxyPreserveHost On
# NE PAS proxifier le challenge Let's Encrypt (sinon le renouvellement TLS casse) :
ProxyPass /.well-known/acme-challenge/ !
ProxyPass / http://127.0.0.1:8001/
ProxyPassReverse / http://127.0.0.1:8001/
# Marquer https UNIQUEMENT sur le vhost SSL (pas sur le :80) :
RequestHeader set X-Forwarded-Proto "https" env=HTTPS
```
Et dans l'onglet **SSL / Redirect** du site, activer la **redirection HTTP→HTTPS**.

**Si ISPConfig utilise nginx** (champ *Directives nginx* du site) :
```nginx
location / {
    proxy_pass http://127.0.0.1:8001;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```
> Pour savoir si c'est Apache ou nginx : `systemctl status apache2` vs `systemctl status nginx` sur le VPS (un seul des deux tourne).

### D. Base de données — ⚠️ PostgreSQL en CLI, PAS via ISPConfig
Le « Serveur BDD » d'ISPConfig gère **MySQL/MariaDB**, que Django **n'utilise pas** ici. Ne PAS créer la base via *Sites → Base de données*. Installer/utiliser **PostgreSQL en ligne de commande** (étape 3) — il tourne en parallèle de MySQL sans conflit (port 5432 ≠ 3306). Vérifier s'il est déjà là : `systemctl status postgresql` ; sinon `sudo apt install -y postgresql` (étape 1).

### E. Le reste
Faire les étapes **1, 2, 4, 5, 6, 7, 9 à 13**. **SAUTER l'étape 8** (nginx/certbot manuels) : ISPConfig s'en charge (B). Garder `DJANGO_X_ACCEL_REDIRECT=False` (Django streame les médias, compatible Apache comme nginx).

---

## 0. Prérequis
- Accès **SSH** au VPS avec un compte **sudo**.
- Un enregistrement DNS **A** (et **AAAA** si IPv6) : `pilot.eve-sn.org` → IP du VPS. À créer chez le gestionnaire DNS d'`eve-sn.org`. Vérifier : `dig +short pilot.eve-sn.org`.
- Le code du projet (ce dépôt) transférable sur le VPS (git ou scp).

## 1. Paquets système
> ⚠️ **Cas ISPConfig (votre serveur) :** PAS d'`apt upgrade` global (risque sur le site/mail en prod), et PAS de nginx/certbot/ufw (ISPConfig gère le web/TLS, le pare-feu existe déjà). Installer **seulement** :
> ```bash
> sudo apt update
> sudo apt install -y python3 python3-venv python3-pip postgresql git
> ```
> (Le script `install.sh` fait exactement cela.)

Cas VPS vierge (hors ISPConfig) uniquement :
```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y python3 python3-venv python3-pip postgresql nginx certbot python3-certbot-nginx git ufw
```

## 2. Utilisateur applicatif + arborescence
```bash
sudo adduser --system --group --home /srv/eve_pilot eve
sudo mkdir -p /srv/eve_pilot /var/www/certbot
sudo chown -R eve:eve /srv/eve_pilot
```

## 3. PostgreSQL
```bash
sudo -u postgres psql <<'SQL'
CREATE USER eve_pilot WITH PASSWORD 'METTRE_UN_MOT_DE_PASSE_FORT';
CREATE DATABASE eve_pilot OWNER eve_pilot;
ALTER ROLE eve_pilot SET client_encoding TO 'utf8';
ALTER ROLE eve_pilot SET timezone TO 'Africa/Dakar';
SQL
```

## 4. Code + environnement Python
```bash
sudo -u eve -H bash
cd /srv/eve_pilot
git clone <URL_DU_DEPOT> .            # ou scp depuis le poste local
python3 -m venv .venv
.venv/bin/pip install --upgrade pip
.venv/bin/pip install -r requirements.txt
exit
```

## 5. Fichier .env de production
```bash
sudo -u eve cp /srv/eve_pilot/.env.production.example /srv/eve_pilot/.env
sudo -u eve nano /srv/eve_pilot/.env      # remplir SECRET_KEY, mots de passe, domaine
sudo chmod 600 /srv/eve_pilot/.env
# Générer la clé secrète :
#   /srv/eve_pilot/.venv/bin/python -c "import secrets; print(secrets.token_urlsafe(64))"
```
Vérifier que le `.env` contient bien `DJANGO_DEBUG=False`, `DJANGO_PROD_SECURITY=True`, `DJANGO_X_ACCEL_REDIRECT=True`, `DJANGO_ALLOWED_HOSTS=pilot.eve-sn.org`.

## 6. Migrations, admin, fichiers statiques
```bash
cd /srv/eve_pilot
sudo -u eve .venv/bin/python manage.py migrate
sudo -u eve .venv/bin/python manage.py createsuperuser
sudo -u eve .venv/bin/python manage.py collectstatic --noinput
# Charger le plan comptable / données de référence si commande dédiée :
# sudo -u eve .venv/bin/python manage.py <seed_...>
```

## 7. Service gunicorn (systemd)
```bash
sudo cp /srv/eve_pilot/deploy/eve_pilot.service /etc/systemd/system/eve_pilot.service
sudo systemctl daemon-reload
sudo systemctl enable --now eve_pilot
sudo systemctl status eve_pilot        # doit être "active (running)"
```

## 8. nginx + certificat TLS
```bash
sudo cp /srv/eve_pilot/deploy/nginx_eve_pilot.conf /etc/nginx/sites-available/eve_pilot
# Adapter le server_name si besoin, puis activer :
sudo ln -s /etc/nginx/sites-available/eve_pilot /etc/nginx/sites-enabled/
sudo rm -f /etc/nginx/sites-enabled/default

# Obtenir le certificat (le DNS doit déjà pointer sur le VPS) :
sudo certbot certonly --webroot -w /var/www/certbot -d pilot.eve-sn.org \
    --agree-tos -m alydiouf@eve-sn.org --no-eff-email
sudo nginx -t && sudo systemctl reload nginx
# Renouvellement auto : certbot installe déjà un timer. Tester :
sudo certbot renew --dry-run
```

## 9. Pare-feu
> 🛑 **NE PAS exécuter sur le VPS ISPConfig de prod.** Activer `ufw` sur un serveur qui fait déjà mail + DNS + web couperait ces services (et possiblement le SSH). Le serveur a déjà ses règles. Étape **réservée à un VPS vierge dédié**. Si tu y tiens malgré tout, il faut d'abord autoriser TOUS les ports en service : SSH (22), 80, 443, panel (8080), mail (25, 465, 587, 143, 993, 110, 995), DNS (53) — sinon tu casses la prod.
```bash
# VPS vierge uniquement :
sudo ufw allow OpenSSH
sudo ufw allow 'Nginx Full'      # 80 + 443
sudo ufw enable
```

## 10. Vérifications (à faire absolument)
```bash
# a) Audit de configuration Django pour la production :
cd /srv/eve_pilot && sudo -u eve .venv/bin/python manage.py check --deploy
#    -> ne doit plus signaler SSL/cookies/HSTS (gérés par DJANGO_PROD_SECURITY).
```
- b) Ouvrir **https://pilot.eve-sn.org/health/** → `{"status":"ok"}`.
- c) `http://pilot.eve-sn.org` redirige bien vers `https://` (cadenas vert).
- d) **Test fuite média (capital)** : se déconnecter, puis ouvrir une URL de justificatif `https://pilot.eve-sn.org/media/...` → doit **renvoyer vers la page de connexion**, jamais le fichier. Et `https://pilot.eve-sn.org/__protected_media__/x` → **404**.
- e) Créer 2-3 comptes de test, envoyer les liens aux collègues SL/Kédougou.

## 11. Mises à jour ultérieures
```bash
cd /srv/eve_pilot
sudo -u eve git pull
sudo -u eve .venv/bin/pip install -r requirements.txt
sudo -u eve .venv/bin/python manage.py migrate
sudo -u eve .venv/bin/python manage.py collectstatic --noinput
sudo systemctl restart eve_pilot
```

## 12. Sauvegardes (à planifier dès le test)
```bash
# Base de données (quotidien recommandé via cron) :
sudo -u postgres pg_dump eve_pilot | gzip > /srv/backups/eve_pilot_$(date +%F).sql.gz
# Médias (pièces justificatives) :
tar czf /srv/backups/media_$(date +%F).tar.gz -C /srv/eve_pilot media
```

## 13. Durcissement complémentaire (recommandé)
- **fail2ban** sur SSH : `sudo apt install fail2ban`.
- Restreindre `/admin/` (le superuser y donne tout pouvoir) : IP autoriste côté nginx, ou au minimum mot de passe très fort + pas de compte « admin/admin ».
- Désactiver le login SSH par mot de passe au profit des clés.
- Surveiller `journalctl -u eve_pilot -f` et `/var/log/nginx/`.

---

### Si le VPS est Windows Server (et non Linux)
Même logique, outils différents : **waitress** (déjà dans requirements) comme serveur WSGI, lancé en **service via NSSM**, derrière **IIS** (module ARR/URL Rewrite) ou **nginx Windows** pour le TLS. Les paramètres Django (`.env`, `DJANGO_PROD_SECURITY`, médias protégés) sont **identiques**. Me le signaler et je fournis les équivalents.
