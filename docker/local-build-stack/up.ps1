$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$composeFile = Join-Path $scriptDir 'compose.yaml'
$envFile = Join-Path $scriptDir '.env'
$exampleEnvFile = Join-Path $scriptDir '.env.example'

if (-not (Test-Path $envFile)) {
    Copy-Item $exampleEnvFile $envFile
    Write-Host 'Created .env from .env.example'
}

& docker compose --env-file $envFile -f $composeFile up -d --build