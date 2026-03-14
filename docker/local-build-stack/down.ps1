param(
    [switch]$RemoveVolumes
)

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$composeFile = Join-Path $scriptDir 'compose.yaml'
$envFile = Join-Path $scriptDir '.env'
$exampleEnvFile = Join-Path $scriptDir '.env.example'
$selectedEnvFile = if (Test-Path $envFile) { $envFile } else { $exampleEnvFile }

$arguments = @('compose', '--env-file', $selectedEnvFile, '-f', $composeFile, 'down', '--remove-orphans')
if ($RemoveVolumes) {
    $arguments += '-v'
}

& docker @arguments