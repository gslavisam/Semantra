param(
    [string]$StreamlitUrl = "",

    [string]$BaseUrl = "",

    [string]$AdminToken = "",

    [switch]$SkipBootstrap,

    [switch]$Headed,

    [switch]$CaptureDemoAssets,

    [switch]$RecordDemoVideo,

    [int]$SlowMoMs = 0,

    [string]$ArtifactsDir = "",

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

if (-not $StreamlitUrl) {
    $StreamlitUrl = if ($env:SEMANTRA_STREAMLIT_URL) { $env:SEMANTRA_STREAMLIT_URL } else { "http://127.0.0.1:8501" }
}

if (-not $BaseUrl) {
    $BaseUrl = if ($env:SEMANTRA_API_BASE_URL) { $env:SEMANTRA_API_BASE_URL } else { "http://127.0.0.1:8000" }
}

if (-not $AdminToken -and $env:SEMANTRA_ADMIN_API_TOKEN) {
    $AdminToken = $env:SEMANTRA_ADMIN_API_TOKEN
}

$arguments = @(
    (Join-Path $scriptDir "run_operational_browser_e2e.py")
    "--streamlit-url"
    $StreamlitUrl
    "--base-url"
    $BaseUrl
)

if ($AdminToken) {
    $arguments += @("--admin-token", $AdminToken)
}

if ($SkipBootstrap) {
    $arguments += "--skip-bootstrap"
}

if ($Headed) {
    $arguments += "--headed"
}

if ($CaptureDemoAssets) {
    $arguments += "--capture-demo-assets"
}

if ($RecordDemoVideo) {
    $arguments += "--record-demo-video"
}

if ($SlowMoMs -gt 0) {
    $arguments += @("--slow-mo-ms", $SlowMoMs)
}

if ($ArtifactsDir) {
    $arguments += @("--artifacts-dir", $ArtifactsDir)
}

& $PythonExecutable $arguments
exit $LASTEXITCODE