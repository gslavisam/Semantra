param(
    [switch]$DryRun,

    [string]$BaseUrl = "",

    [string]$AdminToken = "",

    [string]$DotenvPath = "../.env",

    [string]$PythonExecutable = "d:/py_radno/.venv/Scripts/python.exe"
)

$ErrorActionPreference = "Stop"

function Import-DotenvFile {
    param([string]$Path)

    if (-not (Test-Path $Path)) {
        return
    }

    Get-Content $Path | ForEach-Object {
        $line = $_.Trim()
        if (-not $line -or $line.StartsWith("#") -or -not $line.Contains("=")) {
            return
        }

        $parts = $line.Split("=", 2)
        $key = $parts[0].Trim()
        $value = $parts[1].Trim().Trim('"').Trim("'")
        Set-Item -Path "Env:$key" -Value $value
    }
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$resolvedDotenvPath = Join-Path $scriptDir $DotenvPath

Import-DotenvFile -Path $resolvedDotenvPath

if (-not $BaseUrl) {
    $BaseUrl = if ($env:SEMANTRA_API_BASE_URL) { $env:SEMANTRA_API_BASE_URL } else { "http://127.0.0.1:8000" }
}

if (-not $AdminToken -and $env:SEMANTRA_ADMIN_API_TOKEN) {
    $AdminToken = $env:SEMANTRA_ADMIN_API_TOKEN
}

$arguments = @(
    (Join-Path $scriptDir "bootstrap_operational_smoke.py")
    "--base-url"
    $BaseUrl
)

if ($AdminToken) {
    $arguments += @("--admin-token", $AdminToken)
}

if ($DryRun) {
    $arguments += "--dry-run"
    Write-Host "Resolved dotenv path: $resolvedDotenvPath"
    Write-Host "SEMANTRA_API_BASE_URL=$BaseUrl"
    if ($AdminToken) {
        Write-Host "SEMANTRA_ADMIN_API_TOKEN=<configured>"
    }
    else {
        Write-Host "SEMANTRA_ADMIN_API_TOKEN=<empty>"
    }
    Write-Host "Command: $PythonExecutable $($arguments -join ' ')"
}

& $PythonExecutable $arguments
exit $LASTEXITCODE