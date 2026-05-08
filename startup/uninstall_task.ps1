<#
.SYNOPSIS
    Remove the Personal AI OS scheduled task.
#>

[CmdletBinding()]
param(
    [string]$TaskName = "PersonalAIOS"
)

$ErrorActionPreference = "Stop"

$task = Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
if ($null -eq $task) {
    Write-Host "Task '$TaskName' is not registered. Nothing to do."
    exit 0
}

Stop-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
Write-Host "Removed scheduled task '$TaskName'."
