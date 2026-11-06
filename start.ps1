param([int]$Port = 8765, [switch]$NoBrowser)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (-not (Test-Path -LiteralPath 'frontend/vendor/echarts.min.js')) {
    npm.cmd install --no-audit --no-fund
    if ($LASTEXITCODE -ne 0) { throw 'npm install failed' }
    npm.cmd run vendor
}
$pythonExe = Join-Path $PSScriptRoot '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $pythonExe)) {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Could not create the project Python environment' }
}
& $pythonExe -c "import importlib.util, importlib.metadata, sys; ready=all(importlib.util.find_spec(name) for name in ['fastapi','uvicorn','pandas','numpy','akshare']); sys.exit(0 if ready and importlib.metadata.version('akshare') == '1.20.35' else 1)"
if ($LASTEXITCODE -ne 0) {
    & $pythonExe -m pip install -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Python dependencies failed' }
}
if ($NoBrowser) { & $pythonExe run.py --port $Port --no-browser }
else { & $pythonExe run.py --port $Port }
