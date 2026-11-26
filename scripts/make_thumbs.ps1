# Generate small JPEG previews for the images inside the official competition
# pack so the download page can show a visual grid without shipping the
# 160 MB originals to every visitor.
#
#   pwsh -File scripts/make_thumbs.ps1 -Root docs/contest/pack

param(
    [string]$Root = "docs/contest/pack",
    [int]$Width = 520
)

$ErrorActionPreference = 'Stop'
try { [Console]::OutputEncoding = [System.Text.Encoding]::UTF8 } catch {}
Add-Type -AssemblyName System.Drawing

$src = (Resolve-Path $Root).Path
$out = Join-Path $src '_thumbs'
New-Item -ItemType Directory -Force -Path $out | Out-Null

$images = Get-ChildItem $src -Recurse -File |
    Where-Object { $_.FullName -notmatch '\\_thumbs\\' -and $_.Extension -match '^\.(png|jpe?g|gif|bmp|webp)$' }

Write-Host "thumbnails: $($images.Count) source images"
$made = 0
$failed = 0
foreach ($img in $images) {
    $rel = $img.FullName.Substring($src.Length + 1)
    $name = ($rel -replace '[\\/]', '__') -replace '\.[^.]+$', '.jpg'
    $dest = Join-Path $out $name
    if (Test-Path $dest) { continue }
    $bitmap = $null
    $graphics = $null
    $source = $null
    try {
        $source = [System.Drawing.Image]::FromFile($img.FullName)
        $w = [Math]::Min($Width, $source.Width)
        $h = [int][Math]::Round($source.Height * ($w / $source.Width))
        $bitmap = New-Object System.Drawing.Bitmap $w, $h
        $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $graphics.PixelOffsetMode = [System.Drawing.Drawing2D.PixelOffsetMode]::HighQuality
        $graphics.DrawImage($source, 0, 0, $w, $h)
        $bitmap.Save($dest, [System.Drawing.Imaging.ImageFormat]::Jpeg)
        $made++
    } catch {
        $failed++
        Write-Host "  skip $rel : $($_.Exception.Message)"
    } finally {
        if ($graphics) { $graphics.Dispose() }
        if ($bitmap) { $bitmap.Dispose() }
        if ($source) { $source.Dispose() }
    }
}
$bytes = (Get-ChildItem $out -File | Measure-Object Length -Sum).Sum
Write-Host ("thumbnails: made {0}, failed {1}, total {2:N1} MB" -f $made, $failed, ($bytes / 1MB))
