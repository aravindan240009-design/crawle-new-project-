$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
python -m venv .venv
if ($LASTEXITCODE) { throw 'Virtual environment creation failed' }
& .\.venv\Scripts\python.exe -m pip install --use-feature=truststore -r requirements.lock
if ($LASTEXITCODE) { throw 'Python dependency install failed' }
Push-Location frontend
try {
    $env:NODE_USE_SYSTEM_CA = '1'
    npm.cmd ci
    if ($LASTEXITCODE) { throw 'Frontend dependency install failed' }
    npm.cmd run build
    if ($LASTEXITCODE) { throw 'Frontend build failed' }
} finally { Pop-Location }
Write-Output 'Ready. Run .\scripts\start.ps1 and open http://127.0.0.1:8765'
