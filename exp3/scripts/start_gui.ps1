$ErrorActionPreference = 'Stop'
Set-Location (Split-Path $PSScriptRoot -Parent)
if (-not (Test-Path -LiteralPath '.venv\Scripts\python.exe')) {
    throw 'Run scripts/bootstrap.ps1 first'
}
& .\.venv\Scripts\python.exe -m host.gui
if ($LASTEXITCODE -ne 0) { throw 'GUI exited with an error' }
