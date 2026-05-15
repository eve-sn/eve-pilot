# Lance EVE Pilot en mode UAT sur le LAN avec Waitress.
# A executer depuis la racine du projet :
#   .\scripts\run_uat.ps1
#
# Prerequis :
#   1. .env present a la racine, configure pour UAT (cf. scripts/.env.uat.example)
#   2. Base eve_pilot_uat cloneee (cf. scripts/clone_db_to_uat.ps1)
#   3. Port TCP 8000 ouvert dans le pare-feu Windows :
#        New-NetFirewallRule -DisplayName "EVE Pilot UAT" `
#          -Direction Inbound -Protocol TCP -LocalPort 8000 -Action Allow

$ErrorActionPreference = "Stop"
$env:PYTHONPATH = ".vendor"

$Python = ".\.venv\Scripts\python.exe"
$Port = 8000

Write-Host "1. Verification des prerequis..."
if (-not (Test-Path ".env")) {
    throw ".env absent. Le copier depuis scripts/.env.uat.example et l'adapter."
}
if (-not (Test-Path $Python)) {
    throw "Venv absent : $Python"
}

# Sanity check : DEBUG doit etre False pour l'UAT.
$debug = (Get-Content .env | Select-String "^DJANGO_DEBUG=").ToString()
if ($debug -match "True|true|1|yes") {
    Write-Warning "DJANGO_DEBUG=True dans .env -- A NE PAS FAIRE en UAT (tracebacks visibles)."
}

Write-Host "2. Migration de la base UAT (idempotent)..."
& $Python manage.py migrate --noinput

Write-Host "3. Collecte des fichiers statiques..."
& $Python manage.py collectstatic --noinput

Write-Host "4. Verification de la mise en veille..."
$standby = (powercfg /query SCHEME_CURRENT SUB_SLEEP STANDBYIDLE | Select-String "Index actuel|Current AC").ToString()
if ($standby -match "0x00000000") {
    Write-Host "   veille deja desactivee (OK)"
} else {
    Write-Warning "Cette machine peut se mettre en veille pendant l'UAT (serveur indisponible). Pour desactiver :"
    Write-Warning "  powercfg /change standby-timeout-ac 0"
    Write-Warning "  powercfg /change monitor-timeout-ac 0"
    Write-Warning "Ne pas oublier de retablir apres l'UAT (valeurs par defaut : 30 minutes)."
}

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.InterfaceAlias -notmatch "Loopback|vEthernet" -and $_.IPAddress -notmatch "^169\." } |
       Select-Object -First 1).IPAddress
Write-Host ""
Write-Host "=================================================="
Write-Host "  EVE Pilot UAT - en ecoute sur le LAN"
Write-Host "  URL pour les testeurs : http://${ip}:${Port}/connexion/"
Write-Host "  Ctrl+C pour arreter le serveur."
Write-Host "=================================================="
Write-Host ""

& $Python -m waitress --listen=0.0.0.0:$Port --threads=8 config.wsgi:application
