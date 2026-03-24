$cmdPath = Join-Path $PSScriptRoot 'safeclaw.cmd'
if (-not (Test-Path $cmdPath)) {
    Write-Error "[safeclaw] launcher missing: $cmdPath"
    exit 1
}
& $cmdPath @args
exit $LASTEXITCODE
