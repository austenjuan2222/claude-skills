param(
    [ValidateSet('Check','Apply','Rollback')][string]$Mode = 'Check',
    [string]$Report,
    [string]$Approval,
    [string]$Backup,
    [switch]$Publish,
    [switch]$Scheduled
)
$ErrorActionPreference = 'Stop'
$configFile = Join-Path $PSScriptRoot 'config.json'
$config = Get-Content -LiteralPath $configFile -Raw -Encoding UTF8 | ConvertFrom-Json
if ($Scheduled -and $Mode -eq 'Check') {
    $latestFile = Join-Path $PSScriptRoot 'latest.json'
    if (Test-Path -LiteralPath $latestFile) {
        $last = Get-Content -LiteralPath $latestFile -Raw -Encoding UTF8 | ConvertFrom-Json
        $now = Get-Date
        $days = (([int]$now.DayOfWeek + 6) % 7)
        $due = $now.Date.AddDays(-$days).AddHours(9)
        if ($due -gt $now) { $due = $due.AddDays(-7) }
        $lastCheck = (Get-Item -LiteralPath $latestFile).LastWriteTime
        if ($lastCheck -ge $due -and $last.status -ne 'failed') { exit 0 }
    }
}
$checker = Join-Path $PSScriptRoot 'skill_updater.py'
$commandArgs = @($checker, $Mode.ToLowerInvariant(), '--config', $configFile)
if ($Mode -eq 'Apply') {
    if (-not $Report -or -not $Approval) { throw 'Apply requires -Report and -Approval (the exact report SHA256).' }
    $commandArgs += @('--report', $Report, '--approve', $Approval)
    if ($Publish) { $commandArgs += '--publish' }
}
if ($Mode -eq 'Rollback') {
    if (-not $Backup) { throw 'Rollback requires -Backup.' }
    $commandArgs += @('--backup', $Backup)
}
$log = Join-Path $PSScriptRoot 'update-skills.log'
"$(Get-Date -Format o) START $Mode" | Out-File -LiteralPath $log -Append -Encoding utf8
$output = & $config.python @commandArgs 2>&1
$result = $LASTEXITCODE
$output | Out-File -LiteralPath $log -Append -Encoding utf8
$output | Write-Output
"$(Get-Date -Format o) END $Mode exit=$result" | Out-File -LiteralPath $log -Append -Encoding utf8
if ($Mode -eq 'Check' -and (Test-Path -LiteralPath (Join-Path $PSScriptRoot 'latest.json'))) {
    $latest = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'latest.json') -Raw -Encoding UTF8 | ConvertFrom-Json
    if ($latest.notify) {
        $noticePath = Join-Path $PSScriptRoot 'PENDING-REVIEW.txt'
        "Claude skills: $($latest.status)`r`nChanged files: $($latest.changed_files)`r`nReport: $($latest.report)`r`nApproval: $($latest.approval)`r`nNo installed skills were changed." | Set-Content -LiteralPath $noticePath -Encoding utf8
        try {
            Add-Type -AssemblyName System.Runtime.WindowsRuntime
            [Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.UI.Notifications.ToastNotification, Windows.UI.Notifications, ContentType = WindowsRuntime] | Out-Null
            [Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime] | Out-Null
            $xml = New-Object Windows.Data.Xml.Dom.XmlDocument
            $body = "Claude skills: $($latest.status). $($latest.changed_files) changed files. Open .claude/skills-updater/PENDING-REVIEW.txt. No updates applied."
            $xml.LoadXml('<toast><visual><binding template="ToastGeneric"><text>Claude skills update</text><text>' + [Security.SecurityElement]::Escape($body) + '</text></binding></visual></toast>')
            $toast = [Windows.UI.Notifications.ToastNotification]::new($xml)
            [Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier('Microsoft.Windows.PowerShell').Show($toast)
            "$(Get-Date -Format o) Notification submitted to Windows" | Out-File -LiteralPath $log -Append -Encoding utf8
        } catch {
            "$(Get-Date -Format o) Notification unavailable; review notice saved: $($_.Exception.Message)" | Out-File -LiteralPath $log -Append -Encoding utf8
        }
    }
}
exit $result
