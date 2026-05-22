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

NOTIFICATION_FILE = '/tmp/dynamo/.claude/notifications.jsonl'
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
