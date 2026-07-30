#requires -Version 5.1
<#
    Registers a local Windows scheduled task as a fallback to the GitHub Actions
    workflow. Only useful if you want the alert to run from this machine too;
    the cloud workflow already runs daily at 18:00 IST without the PC being on.
#>
param(
    [string]$PythonExe = 'C:/Users/mohan/AppData/Local/Programs/Python/Python312/python.exe',
    [string]$Workspace = 'D:\Job alert',
    [string]$ToEmail   = 'mohan.leelachemuru@gmail.com',
    [string]$RunAt     = '6:00PM'
)

$runner = Join-Path $Workspace 'scripts\run_daily.ps1'

# The task has to fetch and rebuild before reporting, otherwise it emails
# whatever happened to be left in data/jobs.json from the last manual run.
@"
Set-Location '$Workspace'
& '$PythonExe' scripts/fetch_jobs.py
& '$PythonExe' scripts/job_alert.py build-profile
& '$PythonExe' scripts/job_alert.py report --to '$ToEmail'
& '$PythonExe' scripts/build_dashboard.py
"@ | Set-Content -Path $runner -Encoding utf8

$taskName = 'PersonalJobSearchDaily6PM'
$action   = New-ScheduledTaskAction -Execute 'powershell.exe' `
                -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$runner`"" `
                -WorkingDirectory $Workspace
$trigger  = New-ScheduledTaskTrigger -Daily -At $RunAt
$settings = New-ScheduledTaskSettingsSet -StartWhenAvailable

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
    -Settings $settings -Description 'Fetch, score and email daily job matches.' -Force

Write-Host "Registered scheduled task: $taskName (daily at $RunAt)"
Write-Host "SMTP_* environment variables must be set for the email step to work."
