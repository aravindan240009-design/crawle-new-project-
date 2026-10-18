# Stops only the server launched for this workspace and recorded in data/server.pid.
$ErrorActionPreference = 'Stop'
$radarRoot = Split-Path $PSScriptRoot -Parent
$pidFile = Join-Path $radarRoot 'data\server.pid'
if (!(Test-Path -LiteralPath $pidFile)) { throw 'No recorded background launcher PID; use Ctrl+C in the server terminal.' }
$radarPid = [int](Get-Content -LiteralPath $pidFile)
$launcher = Get-CimInstance Win32_Process -Filter "ProcessId=$radarPid"
$expectedExecutable = Join-Path $radarRoot '.venv\Scripts\python.exe'
if (!$launcher -or $launcher.ExecutablePath -ne $expectedExecutable -or $launcher.CommandLine -notmatch '-m backend serve') {
    throw 'Recorded PID does not identify this workspace server; nothing stopped.'
}
Get-CimInstance Win32_Process -Filter "ParentProcessId=$radarPid" | Where-Object { $_.CommandLine -match '-m backend serve' } | ForEach-Object { Stop-Process -Id $_.ProcessId }
Stop-Process -Id $radarPid -ErrorAction SilentlyContinue
Remove-Item -LiteralPath $pidFile
Write-Output 'Stopped the recorded local server. Active scans recover as interrupted after lease expiry.'
