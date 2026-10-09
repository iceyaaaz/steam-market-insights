$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
$localPython = Join-Path $PSScriptRoot '.venv/Scripts/python.exe'
$workspacePython = Join-Path $PSScriptRoot '../../work/.venv/Scripts/python.exe'
if (Test-Path -LiteralPath $localPython) {
    $appPython = $localPython
} elseif (Test-Path -LiteralPath $workspacePython) {
    $appPython = (Resolve-Path -LiteralPath $workspacePython).Path
} else {
    python -m venv .venv
    if ($LASTEXITCODE -ne 0) { throw 'Python 3.13 is required.' }
    $appPython = $localPython
    & $appPython -m pip install --no-cache-dir -r requirements.txt
    if ($LASTEXITCODE -ne 0) { throw 'Dependency installation failed.' }
}
& $appPython -m streamlit run app.py
