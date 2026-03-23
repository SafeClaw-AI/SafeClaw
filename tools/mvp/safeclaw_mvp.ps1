$ErrorActionPreference = 'Stop'

$cmdPath = Join-Path $PSScriptRoot 'safeclaw_mvp.cmd'
if ($args.Count -eq 0) {
    & $cmdPath
}
else {
    & $cmdPath @args
}

exit $LASTEXITCODE
