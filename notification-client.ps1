# Claude Notification Client for Windows
# Polls the Linux server for notifications and displays popups

$ServerUrl = "http://172.26.46.79:9090/poll"
$PollInterval = 3  # seconds

Add-Type -AssemblyName PresentationFramework

Write-Host "Claude Notification Client Started" -ForegroundColor Green
Write-Host "Polling: $ServerUrl" -ForegroundColor Cyan
Write-Host "Interval: $PollInterval seconds" -ForegroundColor Cyan
Write-Host "Press Ctrl+C to stop`n" -ForegroundColor Yellow

while ($true) {
    try {
        $response = Invoke-RestMethod -Uri $ServerUrl -Method Get -TimeoutSec 5 -ErrorAction Stop

        if ($response -and $response.Count -gt 0) {
            foreach ($notification in $response) {
                $timestamp = $notification.timestamp
                $type = $notification.type

                $message = switch ($type) {
                    'stop' { 'Claude stopped responding' }
                    'permission' { 'Claude is requesting permission' }
                    default { "Claude notification: $type" }
                }

                Write-Host "[$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')] $message" -ForegroundColor Green

                # Show popup that auto-closes after 2 seconds
                $wshell = New-Object -ComObject Wscript.Shell
                $wshell.Popup($message, 2, 'Claude Code Notification', 0x40) | Out-Null
            }
        }
    }
    catch {
        # Silently ignore connection errors (server might not be running)
        # Uncomment to debug:
        # Write-Host "Poll error: $($_.Exception.Message)" -ForegroundColor Red
    }

    Start-Sleep -Seconds $PollInterval
}
