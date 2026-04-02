$scriptPath = Join-Path $PSScriptRoot 'safeclaw_personal_mvp.py'
if (-not (Test-Path $scriptPath)) {
    Write-Error "[personal] launcher missing: $scriptPath"
    exit 1
}
python -X utf8 $scriptPath @args
exit $LASTEXITCODE
