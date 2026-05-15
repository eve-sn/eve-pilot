# Clone la base eve_pilot vers eve_pilot_uat dans le container Docker.
# A executer depuis la racine du projet :
#   .\scripts\clone_db_to_uat.ps1
#
# Idempotent : si eve_pilot_uat existe deja elle est droppee puis recreee.

$ErrorActionPreference = "Stop"

$Container = "eve_pilot_pg"
$User = "postgres"
$Source = "eve_pilot"
$Target = "eve_pilot_uat"

Write-Host "1. Verification du container Docker..."
$state = docker inspect -f "{{.State.Running}}" $Container 2>$null
if ($state -ne "true") {
    throw "Container $Container non demarre. Lancer 'docker start $Container'."
}

Write-Host "2. Dump de $Source..."
$dumpPath = "$env:TEMP\eve_pilot_uat_dump_$(Get-Date -Format yyyyMMdd_HHmmss).sql"
docker exec $Container pg_dump -U $User -d $Source -F p --no-owner --no-acl > $dumpPath
if (-not (Test-Path $dumpPath) -or (Get-Item $dumpPath).Length -eq 0) {
    throw "Dump vide ou absent : $dumpPath"
}
Write-Host "   dump ecrit : $dumpPath ($((Get-Item $dumpPath).Length) octets)"

Write-Host "3. Recreation de $Target..."
docker exec $Container psql -U $User -d postgres -c "DROP DATABASE IF EXISTS $Target;"
docker exec $Container psql -U $User -d postgres -c "CREATE DATABASE $Target;"

Write-Host "4. Import du dump dans $Target..."
Get-Content $dumpPath | docker exec -i $Container psql -U $User -d $Target

Write-Host "5. Verification..."
docker exec $Container psql -U $User -d $Target -c "SELECT count(*) as projects FROM projects;"
docker exec $Container psql -U $User -d $Target -c "SELECT count(*) as activities FROM activities;"

Remove-Item $dumpPath
Write-Host "OK. Base $Target prete. Lancer maintenant run_uat.ps1."
