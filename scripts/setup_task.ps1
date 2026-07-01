param(
    [string]$PythonExe = 'C:/Users/mohan/AppData/Local/Programs/Python/Python312/python.exe',
    [string]$Workspace = 'D:\Job alert'
)

$scriptPath = Join-Path $Workspace 'scripts\job_alert.py'
$taskName = 'PersonalJobSearchDaily6PM'
$action = New-ScheduledTaskAction -Execute $PythonExe -Argument "`"$scriptPath`" report --to mohan.leelachemuru@gmail.com" -WorkingDirectory $Workspace
$trigger = New-ScheduledTaskTrigger -Daily -At 6:00PM
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Description 'Send daily AI and QA job email at 6 PM.' -Force
Write-Host "Registered scheduled task: $taskName"
