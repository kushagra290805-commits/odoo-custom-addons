<#
.SYNOPSIS
    Provision the isolated Phase 44.3 certification database (PC-2 / C-23).

.DESCRIPTION
    Reproducible restore of the development database into an isolated
    certification database. Phase 44.1 §18.0 PC-2 requires certification to run
    against a database restored from a dump of the live DB, never against the
    development database itself.

    Artefacts produced:
      backups\nexora_studio_pre_cert.dump   source dump (binary, not committed)
      artefacts\PC2_cert_db_provisioning.txt provisioning record

.NOTES
    Secrets: this script takes the DB password from the PGPASSWORD environment
    variable. It never writes a password into any artefact.
    The connector master key is NOT handled here — supply it via
    NEXORA_CONNECTOR_SECRET_KEY when running Odoo against the certification DB.

.EXAMPLE
    $env:PGPASSWORD = '<db password>'
    .\provision_cert_db.ps1
#>
[CmdletBinding()]
param(
    [string]$SourceDb   = 'nexora_studio',
    [string]$CertDb     = 'nexora_cert',
    [string]$DbUser     = 'odoo',
    [string]$DbHost     = 'localhost',
    [int]   $DbPort     = 5432,
    [string]$DumpPath   = 'D:\ODOO\backups\nexora_studio_pre_cert.dump',
    [string]$RecordPath = 'D:\ODOO\custom-addons\agency\nexora_studio\docs\reports\artefacts\PC2_cert_db_provisioning.txt'
)

$ErrorActionPreference = 'Stop'

if (-not $env:PGPASSWORD) {
    throw 'PGPASSWORD is not set. Export it before running; it is never stored in this script.'
}
if ($CertDb -eq $SourceDb) {
    throw "Refusing to run: certification DB must differ from the source DB ($SourceDb)."
}

$dumpDir = Split-Path -Parent $DumpPath
New-Item -ItemType Directory -Force -Path $dumpDir | Out-Null

Write-Host "[1/4] Dumping $SourceDb -> $DumpPath"
& pg_dump -U $DbUser -h $DbHost -p $DbPort -Fc -f $DumpPath $SourceDb
if ($LASTEXITCODE -ne 0) { throw "pg_dump failed ($LASTEXITCODE)" }

Write-Host "[2/4] Recreating $CertDb"
& psql -U $DbUser -h $DbHost -p $DbPort -d postgres -c "DROP DATABASE IF EXISTS $CertDb;" | Out-Null
& psql -U $DbUser -h $DbHost -p $DbPort -d postgres -c "CREATE DATABASE $CertDb OWNER $DbUser;" | Out-Null
if ($LASTEXITCODE -ne 0) { throw "CREATE DATABASE failed ($LASTEXITCODE)" }

Write-Host "[3/4] Restoring into $CertDb"
& pg_restore -U $DbUser -h $DbHost -p $DbPort -d $CertDb --no-owner --no-privileges $DumpPath
if ($LASTEXITCODE -ne 0) { throw "pg_restore failed ($LASTEXITCODE)" }

Write-Host "[4/4] Recording provisioning artefact"
$dumpItem   = Get-Item $DumpPath
$dumpSha    = (Get-FileHash -Path $DumpPath -Algorithm SHA256).Hash
$connectors = & psql -U $DbUser -h $DbHost -p $DbPort -d $CertDb -t -A -c 'select count(*) from nexora_connector;'
$tools      = & psql -U $DbUser -h $DbHost -p $DbPort -d $CertDb -t -A -c 'select count(*) from nexora_mcp_discovered_tool;'
$creds      = & psql -U $DbUser -h $DbHost -p $DbPort -d $CertDb -t -A -c 'select count(*) from nexora_mcp_credential;'
$pgver      = & psql -U $DbUser -h $DbHost -p $DbPort -d $CertDb -t -A -c 'show server_version;'

@"
# PC-2 certification database provisioning record
# Phase 44.1 s18.0 PC-2 / s17 C-23

provisioned_at        : $(Get-Date -Format o)
source_database       : $SourceDb
certification_database: $CertDb
postgres_version      : $($pgver.Trim())
method                : pg_dump -Fc  +  pg_restore --no-owner --no-privileges
script                : docs/reports/artefacts/provision_cert_db.ps1
odoo_config           : D:\ODOO\configs\cert.conf  (dbfilter = ^$CertDb$, http_port 8169, data_dir D:\ODOO\data-cert)
master_key_source     : environment variable NEXORA_CONNECTOR_SECRET_KEY only (PC-3)

dump_file             : $DumpPath
dump_bytes            : $($dumpItem.Length)
dump_sha256           : $dumpSha

restored_row_counts:
  nexora_connector            : $($connectors.Trim())
  nexora_mcp_discovered_tool  : $($tools.Trim())
  nexora_mcp_credential       : $($creds.Trim())

secrets_in_artefact   : none (no passwords, no credential values, lengths/hashes only)
"@ | Set-Content -Encoding utf8 $RecordPath

Write-Host "Done. Record: $RecordPath"
