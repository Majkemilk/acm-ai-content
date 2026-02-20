# One-off: fill only the 3 newly generated articles. Other .md are moved out and NOT restored.
# Run from project root: .\scripts\fill_only_these_3_once.ps1

$ErrorActionPreference = "Stop"
$ProjectRoot = Resolve-Path (Join-Path $PSScriptRoot "..")
$ArticlesDir = Join-Path $ProjectRoot "content\articles"
$ExcludedDir = Join-Path $ProjectRoot "content\articles_excluded_from_fill"

$OnlyTheseStems = @(
    "2026-02-20-how-to-leverage-ai-to-automate-the-segmentation-of-email-list-for-targeted-campaigns",
    "2026-02-20-how-to-implement-ai-tools-to-enhance-visual-asset-management-for-marketing-campaigns",
    "2026-02-20-how-to-automate-the-curation-of-user-generated-content-for-brand-promotion-using-ai"
)

if (-not (Test-Path $ArticlesDir)) { Write-Error "Not found: $ArticlesDir"; exit 1 }

# Move every .md that is NOT in the 3 to content\articles_excluded_from_fill (not restored)
New-Item -ItemType Directory -Force -Path $ExcludedDir | Out-Null
$moved = 0
Get-ChildItem -Path $ArticlesDir -Filter "*.md" | ForEach-Object {
    $stem = [System.IO.Path]::GetFileNameWithoutExtension($_.Name)
    if ($stem -notin $OnlyTheseStems) {
        Move-Item -Path $_.FullName -Destination (Join-Path $ExcludedDir $_.Name) -Force
        $moved++
    }
}
Write-Host "Moved $moved other .md file(s) to content\articles_excluded_from_fill (they will not be restored)."

Set-Location $ProjectRoot
python scripts/fill_articles.py --html --write

Write-Host "Done. Excluded articles remain in content\articles_excluded_from_fill (delete folder if you do not need them)."
