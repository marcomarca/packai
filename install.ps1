# install.ps1 - Instalador automático para Pack AI en Windows

$ProjectRoot = $PSScriptRoot
$BinDir = "$env:USERPROFILE\bin"
$CmdFile = Join-Path $BinDir "packai.cmd"

# 0. Verificar requisitos
if (-not (Get-Command uv -ErrorAction SilentlyContinue)) {
    Write-Host "❌ uv no está instalado o no está en el PATH." -ForegroundColor Red
    Write-Host "💡 Instálalo con: powershell -c ""irm https://astral.sh/uv/install.ps1 | iex""" -ForegroundColor Yellow
    exit 1
}

Write-Host "🚀 Iniciando instalación de Pack AI..." -ForegroundColor Cyan

# 1. Crear carpeta bin si no existe
if (!(Test-Path $BinDir)) {
    New-Item -ItemType Directory -Path $BinDir -Force | Out-Null
    Write-Host "✅ Carpeta creada: $BinDir"
}

# 2. Crear el archivo .cmd
$CmdContent = @"
@echo off
set "PackAiProject=$ProjectRoot"
if "%~1" == "" (
    uv run --project "%PackAiProject%" python "%PackAiProject%\pack_ai.py" .
) else (
    uv run --project "%PackAiProject%" python "%PackAiProject%\pack_ai.py" %*
)
"@

Set-Content -Path $CmdFile -Value $CmdContent -Encoding ASCII
Write-Host "✅ Comando generado en: $CmdFile"

# 3. Añadir al PATH del usuario
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if (($UserPath -split ";") -notcontains $BinDir) {
    [Environment]::SetEnvironmentVariable("Path", "$UserPath;$BinDir", "User")
    Write-Host "✅ Carpeta añadida al PATH del usuario." -ForegroundColor Green
    Write-Host "📢 NOTA: Reinicia tu terminal para empezar a usar 'packai'." -ForegroundColor Yellow
} else {
    Write-Host "ℹ️ La carpeta ya estaba en el PATH."
}

Write-Host "✨ Instalación completada con éxito!" -ForegroundColor Cyan
