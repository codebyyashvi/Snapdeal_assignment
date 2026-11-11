# Restart the backend on :8000 (logs in server.log)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*uvicorn app.main*' } | ForEach-Object { Stop-Process -Id $_.ProcessId -Force }
Set-Location $PSScriptRoot
Start-Process -FilePath .\.venv\Scripts\python.exe -ArgumentList "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000" -RedirectStandardOutput server.out.log -RedirectStandardError server.log -WindowStyle Hidden
Start-Sleep 5
Invoke-RestMethod http://127.0.0.1:8000/api/health | ConvertTo-Json -Compress
