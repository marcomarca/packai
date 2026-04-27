# uninstall.ps1 - Desinstalador de Pack AI

$BinDir = "$env:USERPROFILE\bin"
$CmdFile = Join-Path $BinDir "packai.cmd"

Write-Host "🗑️ Iniciando desinstalación de Pack AI..." -ForegroundColor Yellow

# 1. Eliminar el archivo .cmd
if (Test-Path $CmdFile) {
    Remove-Item $CmdFile -Force
    Write-Host "✅ Archivo $CmdFile eliminado."
} else {
    Write-Host "ℹ️ El comando no se encontró en $BinDir."
}

# 2. Quitar del PATH del usuario
$UserPath = [Environment]::GetEnvironmentVariable("Path", "User")
if ($UserPath -like "*$BinDir*") {
    # Filtrar la ruta para quitar el BinDir (manejando puntos y comas)
    $NewPath = ($UserPath -split ";" | Where-Object { $_ -ne $BinDir }) -join ";"
    [Environment]::SetEnvironmentVariable("Path", $NewPath, "User")
    Write-Host "✅ Carpeta eliminada del PATH del usuario." -ForegroundColor Green
    Write-Host "📢 NOTA: Los cambios se reflejarán en nuevas terminales." -ForegroundColor Yellow
}

# 3. Borrar la carpeta bin si está vacía
if (Test-Path $BinDir) {
    $Files = Get-ChildItem $BinDir
    if ($Files.Count -eq 0) {
        Remove-Item $BinDir -Force
        Write-Host "✅ Carpeta $BinDir eliminada por estar vacía."
    }
}

Write-Host "✨ Desinstalación completada con éxito!" -ForegroundColor Cyan
