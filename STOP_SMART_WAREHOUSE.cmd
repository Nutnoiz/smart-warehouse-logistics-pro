@echo off
setlocal
cd /d "%~dp0"
powershell -NoProfile -Command "$projectRoot=(Get-Location).Path+'\'; foreach($port in @(8010,5180)){foreach($connection in @(Get-NetTCPConnection -State Listen -LocalPort $port -ErrorAction SilentlyContinue)){ $process=Get-CimInstance Win32_Process -Filter ('ProcessId='+$connection.OwningProcess); $parent=Get-CimInstance Win32_Process -Filter ('ProcessId='+$process.ParentProcessId); if(($process.CommandLine -and $process.CommandLine.Contains($projectRoot)) -or ($parent.CommandLine -and $parent.CommandLine.Contains($projectRoot))){Stop-Process -Id $process.ProcessId -ErrorAction Stop;Write-Host ('Stopped Warehouse Pro port '+$port)}else{Write-Host ('Port '+$port+' belongs to an unverified process; skipped')}}}"
pause
endlocal
