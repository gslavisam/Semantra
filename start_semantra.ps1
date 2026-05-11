param(
    [int]$ApiPort = 8000,
    [int]$UiPort = 8501,
    [switch]$ReuseCurrentWindow
)

$ErrorActionPreference = "Stop"

function Test-PortListening {
    param([int]$Port)

    try {
        return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop)
    }
    catch {
        return $false
    }
}

function Wait-PortListening {
    param(
        [int]$Port,
        [string]$ServiceName,
        [int]$TimeoutSeconds = 30
    )

    $deadline = [DateTime]::UtcNow.AddSeconds($TimeoutSeconds)
    while ([DateTime]::UtcNow -lt $deadline) {
        if (Test-PortListening -Port $Port) {
            return
        }
        [System.Threading.Thread]::Sleep(250)
    }

    throw "$ServiceName did not start listening on http://127.0.0.1:$Port within $TimeoutSeconds seconds."
}

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$pythonExecutable = [System.IO.Path]::GetFullPath((Join-Path $scriptDir "..\.venv\Scripts\python.exe"))

if (-not (Test-Path $pythonExecutable)) {
    throw "Python executable not found at $pythonExecutable"
}

$backendAppDir = Join-Path $scriptDir "backend"
$backendCommand = "Set-Location '$scriptDir'; & '$pythonExecutable' -m uvicorn app.main:app --reload --app-dir '$backendAppDir' --reload-dir '$backendAppDir' --host 127.0.0.1 --port $ApiPort"
$streamlitCommand = "Set-Location '$scriptDir'; & '$pythonExecutable' -m streamlit run '$scriptDir\streamlit_app.py' --server.headless true --server.address 127.0.0.1 --server.port $UiPort"

if (Test-PortListening -Port $ApiPort) {
    Write-Host "Backend already listening on http://127.0.0.1:$ApiPort"
}
else {
    if ($ReuseCurrentWindow) {
        Start-Job -Name "semantra-backend" -ScriptBlock {
            param($command)
            Invoke-Expression $command
        } -ArgumentList $backendCommand | Out-Null
    }
    else {
        Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $backendCommand | Out-Null
    }

    Write-Host "Starting backend on http://127.0.0.1:$ApiPort"
    Wait-PortListening -Port $ApiPort -ServiceName "Backend"
    Write-Host "Backend is ready on http://127.0.0.1:$ApiPort"
}

if (Test-PortListening -Port $UiPort) {
    Write-Host "Streamlit already listening on http://127.0.0.1:$UiPort"
}
else {
    if ($ReuseCurrentWindow) {
        Start-Job -Name "semantra-streamlit" -ScriptBlock {
            param($command)
            Invoke-Expression $command
        } -ArgumentList $streamlitCommand | Out-Null
    }
    else {
        Start-Process powershell -ArgumentList '-NoExit', '-ExecutionPolicy', 'Bypass', '-Command', $streamlitCommand | Out-Null
    }

    Write-Host "Starting Streamlit on http://127.0.0.1:$UiPort"
    Wait-PortListening -Port $UiPort -ServiceName "Streamlit UI"
    Write-Host "Streamlit is ready on http://127.0.0.1:$UiPort"
}

Write-Host "Semantra endpoints: API=http://127.0.0.1:$ApiPort UI=http://127.0.0.1:$UiPort"