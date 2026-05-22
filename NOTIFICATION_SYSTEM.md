# Claude Code Remote Notifications System

## Design Doc

### Problem
Notify Windows users when Claude pauses (stops responding, requests permissions) from a remote Linux server, across a corporate network that blocks inbound connections.

### Architecture
**Pull-based notification system** (Windows polls Linux, not push)

**Components:**
1. **Claude Hooks** (`.claude/settings.json`) - Capture Stop/PermissionRequest events
2. **Queue File** (`notifications.jsonl`) - JSONL append-only log
3. **HTTP Server** (Python, Linux) - Serves notifications at `/poll` endpoint
4. **Client** (PowerShell, Windows) - Polls server, displays popups

**Flow:**
```
Claude event → Hook writes JSON → Queue file → HTTP GET /poll → PowerShell displays popup
```

### Why This Design
- Corporate firewall blocks inbound to Windows (can't push)
- Outbound from Windows usually allowed (pull works)
- JSONL queue handles multiple rapid events
- Stateless HTTP polling (no persistent connections)
- No dependencies on external services

### Event Types
- `stop` - Claude stopped responding
- `permission` - Claude is requesting permission

---

## Deploy Guide

### Prerequisites
- Linux server accessible from Windows (HTTP outbound allowed)
- Python 3 on Linux server
- PowerShell on Windows (built-in)

### Linux Server Setup (<LINUX_SERVER_IP>)

#### 1. Configure Hooks
Find the correct location of settings.json, if CLAUDE_CONFIG_DIR is set, check this location first.
Edit `.claude/settings.json` additively:
```json
{
  "hooks": {
    "Stop": [{
      "hooks": [{
        "type": "command",
        "command": "echo \"{\\\"type\\\":\\\"stop\\\",\\\"timestamp\\\":\\\"$(date -Iseconds)\\\"}\" >> <project_root>/.claude/notifications.jsonl"
      }]
    }],
    "PermissionRequest": [{
      "hooks": [{
        "type": "command",
        "command": "echo \"{\\\"type\\\":\\\"permission\\\",\\\"timestamp\\\":\\\"$(date -Iseconds)\\\"}\" >> <project_root>/.claude/notifications.jsonl"
      }]
    }]
  }
}
```

#### 2. Start Notification Server

```bash
cd <project_root>
python3 notification-server.py &

# Verify running
curl http://localhost:9090/poll
# Should return: []
```

#### 3. Verify Hooks Working

```bash
# Check notifications are being written
tail -f <project_root>/.claude/notifications.jsonl
```

### Windows Client Setup (<WINDOWS_CLIENT_IP>)

#### 1. Copy PowerShell Script

Copy `notification-client.ps1` from Linux server to Windows machine.

#### 2. Run Client

```powershell
.\notification-client.ps1
```

You should see:
```
Claude Notification Client Started
Polling: http://<LINUX_SERVER_IP>:9090/poll
Interval: 3 seconds
Press Ctrl+C to stop
```

#### 3. Test

Trigger a Claude pause event. Within 3 seconds, you should see a Windows message box popup.

### Troubleshooting

**No popups appearing:**
- Check Windows can reach the server:
  ```powershell
  Invoke-RestMethod -Uri http://<LINUX_SERVER_IP>:9090/poll
  ```
- Check corporate proxy settings
- Verify server is running on Linux

**Server not running:**
```bash
ps aux | grep notification-server
```

**Hooks not firing:**
```bash
# Should grow when Claude pauses
ls -lh <project_root>/.claude/notifications.jsonl
cat <project_root>/.claude/notifications.jsonl
```

**Permission issues:**
```bash
# Ensure notification file is writable
chmod 666 <project_root>/.claude/notifications.jsonl
```

---

## Scripts

### Python Server (notification-server.py)

Save as `<project_root>/notification-server.py`:

```python
#!/usr/bin/env python3
"""
Claude Notification Server
Serves notifications that hooks write to a queue file
"""
import http.server
import json
import os
import threading
import time
from pathlib import Path

NOTIFICATION_FILE = '<project_root>/.claude/notifications.jsonl'
PORT = 9090

class NotificationHandler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/poll':
            # Return all pending notifications and clear the file
            notifications = []
            if os.path.exists(NOTIFICATION_FILE):
                try:
                    with open(NOTIFICATION_FILE, 'r') as f:
                        for line in f:
                            line = line.strip()
                            if line:
                                notifications.append(json.loads(line))
                    # Clear the file after reading
                    open(NOTIFICATION_FILE, 'w').close()
                except Exception as e:
                    print(f"Error reading notifications: {e}")

            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(notifications).encode())
        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, format, *args):
        # Custom logging
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {args[0]}")

if __name__ == '__main__':
    # Ensure notification file directory exists
    Path(NOTIFICATION_FILE).parent.mkdir(parents=True, exist_ok=True)

    server = http.server.HTTPServer(('0.0.0.0', PORT), NotificationHandler)
    print(f"Notification server started on http://0.0.0.0:{PORT}")
    print(f"Windows should poll: http://<LINUX_SERVER_IP>:{PORT}/poll")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        server.shutdown()
```

Make executable:
```bash
chmod +x notification-server.py
```

### PowerShell Client (notification-client.ps1)

Save as `notification-client.ps1`:

```powershell
# Claude Notification Client for Windows
# Polls the Linux server for notifications and displays popups

$ServerUrl = "http://<LINUX_SERVER_IP>:9090/poll"
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

                # Show popup
                [System.Windows.MessageBox]::Show($message, 'Claude Code Notification', [System.Windows.MessageBoxButton]::OK, [System.Windows.MessageBoxImage]::Information) | Out-Null
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
```

---

## Configuration Reference

### Hook Configuration

To add more event types, edit `.claude/settings.json`:

```json
{
  "hooks": {
    "EventName": [{
      "hooks": [{
        "type": "command",
        "command": "echo \"{\\\"type\\\":\\\"custom_event\\\",\\\"timestamp\\\":\\\"$(date -Iseconds)\\\"}\" >> <project_root>/.claude/notifications.jsonl"
      }]
    }]
  }
}
```

Available hook events:
- `Stop` - When Claude stops responding
- `PermissionRequest` - When permission is needed
- `SessionStart` - When session starts
- `PreToolUse` - Before tool execution
- `PostToolUse` - After tool execution

---

## API Reference

### GET /poll

Returns all pending notifications and clears the queue.

**Response:**
```json
[
  {
    "type": "stop",
    "timestamp": "2025-01-15T10:30:00+00:00"
  },
  {
    "type": "permission",
    "timestamp": "2025-01-15T10:31:15+00:00"
  }
]
```

**Status Codes:**
- `200 OK` - Success (may return empty array `[]`)
- `404 Not Found` - Invalid endpoint


---

## Security Considerations

- HTTP server runs on all interfaces (`0.0.0.0`)
- No authentication required (assumes trusted network)
- Notifications may contain sensitive timestamp information
- For production: Add HTTPS, authentication, and rate limiting

---
