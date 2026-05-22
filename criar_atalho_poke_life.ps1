$ErrorActionPreference = "Stop"

$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
$Launcher = Join-Path $Root "Poke Life.pyw"
$Icon = Join-Path $Root "web\static\poke_life.ico"
$DesktopShortcutPath = Join-Path ([Environment]::GetFolderPath("Desktop")) "Poke Life.lnk"
$FolderShortcutPath = Join-Path $Root "Poke Life.lnk"

function Find-Pythonw {
    $cmd = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($cmd) { return $cmd.Source }

    $py = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($py) { return $py.Source }

    throw "pythonw.exe ou py.exe nao foi encontrado no PATH."
}

function Write-PokeLifeIcon {
    param([string]$Path)

    if (Test-Path -LiteralPath $Path) { return }

    Add-Type -AssemblyName System.Drawing
    $dir = Split-Path -Parent $Path
    if (!(Test-Path -LiteralPath $dir)) {
        New-Item -ItemType Directory -Path $dir | Out-Null
    }

    $bmp = New-Object System.Drawing.Bitmap 64, 64
    $gfx = [System.Drawing.Graphics]::FromImage($bmp)
    $gfx.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $gfx.Clear([System.Drawing.Color]::Transparent)

    $green = [System.Drawing.Brushes]::MediumSeaGreen
    $cream = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 255, 253, 248))
    $dark = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(255, 37, 35, 31))
    $pen = New-Object System.Drawing.Pen ([System.Drawing.Color]::FromArgb(255, 37, 35, 31)), 3

    $gfx.FillEllipse($green, 4, 4, 56, 56)
    $gfx.DrawLine($pen, 12, 32, 52, 32)
    $gfx.FillEllipse($cream, 24, 24, 16, 16)
    $gfx.DrawEllipse($pen, 24, 24, 16, 16)

    $font = New-Object System.Drawing.Font "Segoe UI", 11, ([System.Drawing.FontStyle]::Bold)
    $format = New-Object System.Drawing.StringFormat
    $format.Alignment = [System.Drawing.StringAlignment]::Center
    $format.LineAlignment = [System.Drawing.StringAlignment]::Center
    $gfx.DrawString("PL", $font, $dark, (New-Object System.Drawing.RectangleF 0, 38, 64, 18), $format)

    $handle = $bmp.GetHicon()
    $icon = [System.Drawing.Icon]::FromHandle($handle)
    $stream = [System.IO.File]::Open($Path, [System.IO.FileMode]::Create)
    try {
        $icon.Save($stream)
    } finally {
        $stream.Close()
        $icon.Dispose()
        $gfx.Dispose()
        $bmp.Dispose()
    }
}

if (!(Test-Path -LiteralPath $Launcher)) {
    throw "Launcher nao encontrado: $Launcher"
}

$Pythonw = Find-Pythonw
Write-PokeLifeIcon -Path $Icon

$shell = New-Object -ComObject WScript.Shell

function New-PokeLifeShortcut {
    param([string]$ShortcutPath)

    $shortcut = $shell.CreateShortcut($ShortcutPath)

    if ((Split-Path -Leaf $Pythonw).ToLowerInvariant() -eq "py.exe") {
        $shortcut.TargetPath = $Pythonw
        $shortcut.Arguments = "-3w `"$Launcher`""
    } else {
        $shortcut.TargetPath = $Pythonw
        $shortcut.Arguments = "`"$Launcher`""
    }

    $shortcut.WorkingDirectory = $Root
    $shortcut.IconLocation = "$Icon,0"
    $shortcut.Description = "Abrir Poke Life no navegador sem janela de console."
    $shortcut.Save()
}

New-PokeLifeShortcut -ShortcutPath $FolderShortcutPath
New-PokeLifeShortcut -ShortcutPath $DesktopShortcutPath

Write-Host "Atalho criado na pasta: $FolderShortcutPath"
Write-Host "Atalho criado na Area de Trabalho: $DesktopShortcutPath"
