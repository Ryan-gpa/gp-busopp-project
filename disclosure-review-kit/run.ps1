<#
  Disclosure Review Kit — one-command runner.

  Examples:
    .\run.ps1 -Report "C:\path\to\NVU Annual Report.pdf"
    .\run.ps1 -Report ".\input\report.pdf" -Ticker NVU -Type annual -DownloadAsx
    .\run.ps1 -Report ".\input\half.pdf" -NoAsx

  Output: .\output\findings.json  and  .\output\<Entity>_Disclosure_Review.docx
#>
param(
  [Parameter(Mandatory = $true)][string]$Report,
  [string]$Ticker,
  [ValidateSet("auto", "interim", "annual")][string]$Type = "auto",
  [switch]$NoAsx,
  [switch]$DownloadAsx,
  [switch]$AsOfPeriod,
  [string]$Materiality
)

$ErrorActionPreference = "Stop"
$kit = $PSScriptRoot
$py  = "python"
$env:PYTHONIOENCODING = "utf-8"

$reviewArgs = @("$kit\lib\review.py", "--report", $Report, "--type", $Type)
if ($Ticker)      { $reviewArgs += @("--ticker", $Ticker) }
if ($NoAsx)       { $reviewArgs += "--no-asx" }
if ($DownloadAsx) { $reviewArgs += "--download-asx" }
if ($AsOfPeriod)  { $reviewArgs += "--as-of-period" }
if ($Materiality) { $reviewArgs += @("--materiality", $Materiality) }

Write-Host "== Step 1/2: review & checklist ==" -ForegroundColor Cyan
& $py @reviewArgs
if ($LASTEXITCODE -ne 0) { throw "review.py failed ($LASTEXITCODE)" }

# derive entity name for the output filename
$findings = Get-Content "$kit\output\findings.json" -Raw | ConvertFrom-Json
$safe = ($findings.entity -replace '[^A-Za-z0-9]+', '_').Trim('_')
$out  = "$kit\output\${safe}_Disclosure_Review.docx"

Write-Host "== Step 2/2: build Word report ==" -ForegroundColor Cyan
& node "$kit\lib\build_report.js" "$kit\output\findings.json" $out
if ($LASTEXITCODE -ne 0) { throw "build_report.js failed ($LASTEXITCODE)" }

Write-Host "`nDone. Report: $out" -ForegroundColor Green
