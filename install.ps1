# install.ps1 - Instalador automático para Pack AI en Windows

param(
    [switch]$NoGui
)

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

# Sincronizar exactamente el lockfile del repositorio. La GUI se instala por
# defecto; usa -NoGui en equipos que solo necesiten el CLI.
$SyncArguments = @("sync", "--project", $ProjectRoot, "--locked")
if (-not $NoGui) {
    $SyncArguments += @("--extra", "gui")
}

& uv @SyncArguments
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ No se pudo sincronizar el proyecto con uv.lock." -ForegroundColor Red
    Write-Host "💡 Después de integrar cambios en pyproject.toml ejecuta primero: uv lock" -ForegroundColor Yellow
    exit $LASTEXITCODE
}

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
    uv run --project "%PackAiProject%" packai .
) else (
    uv run --project "%PackAiProject%" packai %*
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

if ($NoGui) {
    Write-Host "ℹ️ Instalación CLI completada sin dependencias gráficas."
} else {
    Write-Host "ℹ️ Interfaz gráfica disponible con: packai gui ."
}
Write-Host "✨ Instalación completada con éxito!" -ForegroundColor Cyan
