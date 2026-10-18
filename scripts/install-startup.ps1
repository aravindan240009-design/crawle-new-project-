# Explicitly run this script only if you want Radar to start at Windows logon.
$ErrorActionPreference = 'Stop'
$startScript = Join-Path $PSScriptRoot 'start.ps1'
$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument ('-NoProfile -WindowStyle Hidden -File "{0}"' -f $startScript)
$trigger = New-ScheduledTaskTrigger -AtLogOn -User ([Security.Principal.WindowsIdentity]::GetCurrent().Name)
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero)
Register-ScheduledTask -TaskName 'Global Opportunity Radar' -Action $action -Trigger $trigger -Settings $settings -Description 'Start the local Radar server at logon; the app owns scan scheduling.'
