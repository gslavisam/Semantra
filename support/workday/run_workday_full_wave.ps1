param(
    [switch]$SkipCanonicalEnrichment
)

$ErrorActionPreference = "Stop"

$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$repoRoot = Resolve-Path (Join-Path $scriptDir "..\..")

$pythonCandidates = @(
    (Join-Path $repoRoot ".venv\Scripts\python.exe"),
    (Join-Path (Split-Path -Parent $repoRoot) ".venv\Scripts\python.exe")
)

$pythonExe = $pythonCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1

if (-not $pythonExe) {
    throw "Python executable not found. Tried: $($pythonCandidates -join ', ')"
}

Set-Location $repoRoot
$env:PYTHONPATH = "backend"

function Run-Step {
    param(
        [string]$Label,
        [string]$ScriptPath
    )

    Write-Host "`n=== $Label ===" -ForegroundColor Cyan
    & $pythonExe $ScriptPath
    if ($LASTEXITCODE -ne 0) {
        throw "Step failed: $ScriptPath"
    }
}

# 1) Build Workday webservice inventory from hr_wd.xml
Run-Step -Label "Webservice inventory" -ScriptPath "support/workday/generate_workday_webservice_inventory.py"

# 2) Datahub classification and promotion waves
Run-Step -Label "Datahub classification" -ScriptPath "support/workday/generate_workday_datahub_inventory.py"
Run-Step -Label "Datahub wave-1 promotion" -ScriptPath "support/workday/promote_workday_canonical_matches.py"
Run-Step -Label "Datahub wave-2 promotion" -ScriptPath "support/workday/promote_workday_canonical_expansions.py"
Run-Step -Label "Datahub context materialization" -ScriptPath "support/workday/materialize_workday_canonical_contexts.py"
Run-Step -Label "Datahub review prioritization" -ScriptPath "support/workday/prioritize_workday_review_queue.py"
Run-Step -Label "Datahub overlay generation" -ScriptPath "support/workday/generate_wd_knowledge_overlay.py"

# 3) Webservice classification and promotion waves
Run-Step -Label "Webservice classification" -ScriptPath "support/workday/generate_workday_webservice_canonical_inventory.py"
Run-Step -Label "Webservice wave-1 promotion" -ScriptPath "support/workday/promote_workday_webservice_canonical_matches.py"
Run-Step -Label "Webservice wave-2 promotion" -ScriptPath "support/workday/promote_workday_webservice_canonical_expansions.py"
Run-Step -Label "Webservice overlay generation" -ScriptPath "support/workday/generate_wd_webservice_knowledge_overlay.py"

if (-not $SkipCanonicalEnrichment) {
    Run-Step -Label "Canonical field-context enrichment" -ScriptPath "support/workday/enrich_canonical_field_contexts_with_wd.py"
    Run-Step -Label "Canonical glossary enrichment" -ScriptPath "support/workday/enrich_canonical_glossary_with_wd.py"
} else {
    Write-Host "`n=== Skipping canonical enrichment (requested) ===" -ForegroundColor Yellow
}

Write-Host "`n=== Output Summary ===" -ForegroundColor Green
$summaryFiles = @(
    "knowledge_sources/generated/runtime/workday/hr_wd_webservice_inventory.csv",
    "knowledge_sources/generated/runtime/workday/workday_datahub_classification.csv",
    "knowledge_sources/generated/runtime/workday/workday_webservice_classification.csv",
    "knowledge_sources/generated/runtime/workday/workday_webservice_promoted_canonical_aliases.csv",
    "knowledge_sources/generated/runtime/workday/workday_webservice_wave2_promoted_canonical_expansions.csv",
    "knowledge_sources/generated/overlays/wd_webservice_knowledge_overlay.csv",
    "metadata_dict/wd_hr_knowledge_overlay.csv",
    "metadata_dict/wd_datahub_knowledge_overlay.csv"
)

foreach ($file in $summaryFiles) {
    if (Test-Path $file) {
        $count = (Get-Content $file | Measure-Object -Line).Lines
        Write-Host "$file => $count lines"
    } else {
        Write-Host "$file => MISSING" -ForegroundColor Red
    }
}

Write-Host "`nWorkday full wave completed." -ForegroundColor Green
