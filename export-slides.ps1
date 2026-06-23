param(
    [Parameter(Mandatory=$true)][string]$Pptx,
    [Parameter(Mandatory=$true)][string]$OutDir
)
$ErrorActionPreference = "Stop"
if (-not (Test-Path $OutDir)) { New-Item -ItemType Directory -Force -Path $OutDir | Out-Null }
$abs = (Resolve-Path $Pptx).Path
$outAbs = (Resolve-Path $OutDir).Path
$pp = New-Object -ComObject PowerPoint.Application
try {
    $deck = $pp.Presentations.Open($abs, $true, $true, $false)
    $deck.SaveAs($outAbs, 18)  # 18 = ppSaveAsPNG (one PNG per slide)
    $deck.Close()
} finally {
    $pp.Quit()
}
Write-Host "OK"
