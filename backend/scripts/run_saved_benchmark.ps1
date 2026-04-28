param(
    [Parameter(Mandatory = $true)]
    [int]$DatasetId,

    [switch]$WithLlm,

    [switch]$DryRun,

    [int]$ShowRuns = 5,

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

$arguments = @(
    (Join-Path $scriptDir "run_saved_benchmark.py")
    "--dataset-id"
    $DatasetId
    "--show-runs"
    $ShowRuns
)

if ($WithLlm) {
    $arguments += "--with-llm"
}

if (-not $env:SEMANTRA_API_BASE_URL) {
    $env:SEMANTRA_API_BASE_URL = "http://127.0.0.1:8000"
}

if ($DryRun) {
    Write-Host "Resolved dotenv path: $resolvedDotenvPath"
    Write-Host "SEMANTRA_API_BASE_URL=$($env:SEMANTRA_API_BASE_URL)"
    if ($env:SEMANTRA_ADMIN_API_TOKEN) {
        Write-Host "SEMANTRA_ADMIN_API_TOKEN=<configured>"
    }
    else {
        Write-Host "SEMANTRA_ADMIN_API_TOKEN=<empty>"
    }
    Write-Host "Command: $PythonExecutable $($arguments -join ' ')"
    exit 0
}

& $PythonExecutable $arguments
exit $LASTEXITCODE