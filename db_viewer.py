import http.server
import json
import os
import sqlite3
import socketserver
import webbrowser

DB_PATH = 'data/sales_agent.db'
PORT = 8003

HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="ru">
<head>
    <meta charset="UTF-8">
    <title>Sales Agent DB Live Viewer</title>
    <style>
        * { box-sizing: border-box; }
        body { 
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, monospace; 
            background: #121212; 
            color: #e0e0e0; 
            margin: 0; 
            padding: 12px; 
            height: 100vh; 
            display: flex; 
            flex-direction: column; 
        }
        h1 { 
            margin: 0 0 10px 0; 
            font-size: 15px; 
            color: #777; 
            border-bottom: 1px solid #222; 
            padding-bottom: 6px; 
            flex-shrink: 0; 
        }
        .container { 
            display: flex; 
            gap: 12px; 
            flex: 1; 
            min-height: 0; 
        }
        .column { 
            flex: 1; 
            background: #181818; 
            border-radius: 6px; 
            border: 1px solid #262626; 
            display: flex; 
            flex-direction: column; 
            min-height: 0; 
            padding: 10px; 
        }
        .column h2 { 
            font-size: 13px; 
            margin: 0 0 8px 0; 
            color: #999; 
            border-bottom: 1px solid #222; 
            padding-bottom: 6px; 
            flex-shrink: 0;
        }
        .content { 
            flex: 1; 
            overflow-y: auto; 
            padding-right: 4px; 
        }
        
        /* Стилизация тонкого аккуратного скроллбара */
        .content::-webkit-scrollbar { width: 5px; }
        .content::-webkit-scrollbar-track { background: transparent; }
        .content::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        .content::-webkit-scrollbar-thumb:hover { background: #555; }

        .card { 
            background: #202020; 
            border-radius: 4px; 
            padding: 8px 10px; 
            margin-bottom: 6px; 
            border: 1px solid #2a2a2a; 
            font-size: 13px;
            line-height: 1.35;
        }
        .header { 
            font-size: 11px; 
            color: #777; 
            display: flex; 
            gap: 6px; 
            align-items: center; 
            margin-bottom: 4px; 
        }
        .badge { 
            padding: 1px 5px; 
            border-radius: 3px; 
            font-weight: bold; 
            font-size: 10px; 
            text-transform: uppercase; 
        }
        .badge-user { background: #2e7d32; color: #fff; }
        .badge-model { background: #00838f; color: #fff; }
        .badge-tool { background: #f57f17; color: #fff; }
        
        .msg-text {
            white-space: pre-wrap;
            word-break: break-word;
            color: #d4d4d4;
        }
        
        .api-info {
            font-size: 12px;
            margin-top: 2px;
        }
        .status-success { color: #4caf50; font-weight: bold; }
        .status-error { color: #f44336; font-weight: bold; }
        .error-box { background: #2a1212; color: #ff8a80; padding: 4px 6px; border-radius: 3px; margin-top: 4px; font-size: 11px; }
        .meta { color: #666; font-size: 11px; margin-top: 3px; }
    </style>
</head>
<body>
    <h1>Sales Agent DB Viewer (Live Auto-refresh 2s)</h1>
    <div class="container">
        <div class="column">
            <h2>Messages (Первые 100)</h2>
            <div id="messages" class="content"></div>
        </div>
        <div class="column">
            <h2>API Calls (Первые 100)</h2>
            <div id="api_calls" class="content"></div>
        </div>
    </div>

    <script>
        async function loadData() {
            try {
                const res = await fetch('/api/data');
                const data = await res.json();
                
                const msgBox = document.getElementById('messages');
                msgBox.innerHTML = data.messages.map(m => {
                    const badgeClass = m.role === 'user' ? 'badge-user' : (m.role === 'model' ? 'badge-model' : 'badge-tool');
                    return `
                        <div class="card">
                            <div class="header">
                                <span>[${m.created_at}]</span>
                                <span class="badge ${badgeClass}">${m.role}</span>
                                <span>(archived: ${m.archived})</span>
                            </div>
                            <div class="msg-text">${escapeHtml(m.text)}</div>
                        </div>
                    `;
                }).join('');

                const apiBox = document.getElementById('api_calls');
                apiBox.innerHTML = data.api_calls.map(a => {
                    const statusClass = a.status === 'SUCCESS' ? 'status-success' : 'status-error';
                    return `
                        <div class="card">
                            <div class="header">
                                <span>[${a.created_at}] ID:${a.id}</span>
                                <span class="${statusClass}">${a.status}</span>
                                <span style="color:#00bcd4">Model: ${a.model}</span>
                            </div>
                            <div class="api-info">
                                <span style="color:#ffb74d">Purpose: ${escapeHtml(a.purpose || '-')}</span> 
                                <span style="color:#666">| MsgID: ${a.in_reply_to_message_id || '-'}</span>
                            </div>
                            <div class="meta">Tokens: in:${a.prompt_tokens} / out:${a.completion_tokens} | Time: ${a.duration_ms}ms</div>
                            ${a.error ? `<div class="error-box">Error: ${escapeHtml(a.error)}</div>` : ''}
                        </div>
                    `;
                }).join('');

            } catch (e) {
                console.error("Error fetching data", e);
            }
        }

        function escapeHtml(text) {
            if (!text) return '';
            return text.replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;");
        }

        loadData();
        setInterval(loadData, 2000);
    </script>
</body>
</html>
"""

class Handler(http.server.SimpleHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/':
            self.send_response(200)
            self.send_header('Content-type', 'text/html; charset=utf-8')
            self.end_headers()
            self.wfile.write(HTML_TEMPLATE.encode('utf-8'))
        elif self.path == '/api/data':
            self.send_response(200)
            self.send_header('Content-type', 'application/json')
            self.end_headers()
            
            messages, api_calls = [], []
            if os.path.exists(DB_PATH):
                con = sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True)
                con.row_factory = sqlite3.Row
                messages = [dict(r) for r in con.execute('SELECT created_at, role, text, archived FROM messages LIMIT 100').fetchall()]
                api_calls = [dict(r) for r in con.execute('SELECT id, created_at, status, model, purpose, in_reply_to_message_id, prompt_tokens, completion_tokens, duration_ms, error FROM api_calls LIMIT 100').fetchall()]
                con.close()
                
            data = json.dumps({'messages': messages, 'api_calls': api_calls}, ensure_ascii=False)
            self.wfile.write(data.encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

if __name__ == '__main__':
    print(f"Сервер запущен! Открываем http://localhost:{PORT}")
    webbrowser.open(f"http://localhost:{PORT}")
    with socketserver.TCPServer(("", PORT), Handler) as httpd:
        httpd.serve_forever()