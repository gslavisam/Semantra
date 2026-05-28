param(
    [string]$StreamlitUrl = "",

    [string]$BaseUrl = "",

    [string]$AdminToken = "",

    [switch]$SkipBootstrap,

    [switch]$Headed,

    [switch]$RecordVideo,

    [switch]$CaptureScreenshots,

    [int]$SlowMoMs = 0,

    [string]$Scenarios = "standard_two_file_mapping,canonical_source_mapping,llm_decision_flow,workspace_output_generation",

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
    (Join-Path $scriptDir "run_workspace_demo_recordings.py")
    "--streamlit-url"
    $StreamlitUrl
    "--base-url"
    $BaseUrl
    "--scenarios"
    $Scenarios
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

if ($RecordVideo) {
    $arguments += "--record-video"
}

if ($CaptureScreenshots) {
    $arguments += "--capture-screenshots"
}

if ($SlowMoMs -gt 0) {
    $arguments += @("--slow-mo-ms", $SlowMoMs)
}

if ($ArtifactsDir) {
    $arguments += @("--artifacts-dir", $ArtifactsDir)
}

& $PythonExecutable $arguments
exit $LASTEXITCODE