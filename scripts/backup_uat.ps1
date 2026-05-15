# Sauvegarde quotidienne de la base UAT.
# A executer manuellement, ou planifie via le Planificateur de taches Windows.
#
# Conserve les 14 derniers dumps dans backups/uat/.

$ErrorActionPreference = "Stop"

$Container = "eve_pilot_pg"
$User = "postgres"
$Db = "eve_pilot_uat"
$BackupDir = "backups\uat"
$Retention = 14  # nombre de dumps conserves

if (-not (Test-Path $BackupDir)) {
    New-Item -ItemType Directory -Path $BackupDir | Out-Null
}

$timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$outFile = Join-Path $BackupDir "eve_pilot_uat_${timestamp}.sql.gz"

Write-Host "Sauvegarde $Db -> $outFile..."
docker exec $Container pg_dump -U $User -d $Db -F p --no-owner --no-acl | `
    & "C:\Program Files\Git\usr\bin\gzip.exe" > $outFile

if (-not (Test-Path $outFile) -or (Get-Item $outFile).Length -lt 1024) {
    throw "Dump vide ou trop petit : $outFile"
}
Write-Host ("   {0:N0} octets ecrits" -f (Get-Item $outFile).Length)

# Nettoyage : on garde les N derniers dumps.
Get-ChildItem $BackupDir -Filter "eve_pilot_uat_*.sql.gz" |
    Sort-Object LastWriteTime -Descending |
    Select-Object -Skip $Retention |
    ForEach-Object {
        Write-Host "   supprime ancien dump : $($_.Name)"
        Remove-Item $_.FullName
    }

Write-Host "OK."
