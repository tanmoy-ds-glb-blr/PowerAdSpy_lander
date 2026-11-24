@echo off
cd /d "%~dp0"
echo Stopping new_lander.py, quick_run_sample_ads.py, test_sample_ads.py and all multiprocessing workers...

powershell -NoProfile -Command "Get-CimInstance Win32_Process | Where-Object { ($_.CommandLine -like '*new_lander.py*' -or $_.CommandLine -like '*quick_run_sample_ads.py*' -or $_.CommandLine -like '*test_sample_ads.py*' -or $_.CommandLine -like '*from multiprocessing*') -and $_.ExecutablePath -like '*python*' } | ForEach-Object { Write-Host 'Stopping PID:' $_.ProcessId; Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }"

echo Cleaning up Chrome processes...
taskkill /F /IM chrome.exe /T 2> nul
taskkill /F /IM chromedriver.exe /T 2> nul

echo All landers, sample runners, and workers stopped.
