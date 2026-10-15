@echo off
cd /d "%~dp0"
echo Stop the Backend window before creating a demo backup.
pause
powershell -NoProfile -Command "$target=Join-Path (Get-Location) ('backups\demo-'+(Get-Date -Format yyyyMMdd-HHmmss)); New-Item -ItemType Directory -Path $target -ErrorAction Stop | Out-Null; Copy-Item -LiteralPath 'backend\warehouse-pro.db' -Destination $target -ErrorAction Stop; if(Test-Path -LiteralPath 'backend\uploads'){Copy-Item -LiteralPath 'backend\uploads' -Destination $target -Recurse}; Write-Host ('Backup created: '+$target)"
if errorlevel 1 echo Backup failed. See the error above.
pause
