$ErrorActionPreference = "Stop"

$ReportDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$BuildDir = Join-Path $ReportDir "build_final"
$JobName = "intelligence_collection_agent_report"

New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

Push-Location $ReportDir
try {
    xelatex -interaction=nonstopmode -halt-on-error -file-line-error `
        -output-directory="$BuildDir" "$JobName.tex"
    if ($LASTEXITCODE -ne 0) { throw "First XeLaTeX pass failed." }
    biber --input-directory="$BuildDir" --output-directory="$BuildDir" $JobName
    if ($LASTEXITCODE -ne 0) { throw "Biber failed." }
    xelatex -interaction=nonstopmode -halt-on-error -file-line-error `
        -output-directory="$BuildDir" "$JobName.tex"
    if ($LASTEXITCODE -ne 0) { throw "Second XeLaTeX pass failed." }
    xelatex -interaction=nonstopmode -halt-on-error -file-line-error `
        -output-directory="$BuildDir" "$JobName.tex"
    if ($LASTEXITCODE -ne 0) { throw "Final XeLaTeX pass failed." }

    $LogPath = Join-Path $BuildDir "$JobName.log"
    $LogText = Get-Content -LiteralPath $LogPath -Raw
    if ($LogText -match 'Overfull|undefined references|Empty bibliography|Please \(re\)run|No driver') {
        throw "Layout, citation, or bibliography warning remains in $LogPath"
    }
    if ($LogText -notmatch 'Output written on[\s\S]*?\(([0-9]+) pages\)') {
        throw "Could not verify page count in $LogPath"
    }
    if ([int]$Matches[1] -lt 90) {
        throw "Report is unexpectedly short: $($Matches[1]) pages"
    }

    Copy-Item -LiteralPath (Join-Path $BuildDir "$JobName.pdf") `
        -Destination (Join-Path $ReportDir "$JobName.pdf") -Force

    $FinalPdf = Join-Path $ReportDir "$JobName.pdf"
    if ((Get-Item -LiteralPath $FinalPdf).Length -lt 100000) {
        throw "Built PDF is unexpectedly small: $FinalPdf"
    }
}
finally {
    Pop-Location
}

Write-Host "Built: $(Join-Path $ReportDir "$JobName.pdf")"
