import os
import sqlite3
import subprocess
from flask import Flask, render_template, jsonify, request

app = Flask(__name__)

# Pełna ścieżka systemowa do roota projektu i bazy
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DB_PATH = os.path.join(BASE_DIR, "polymarket_anomalies.db")

def init_alerts_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''CREATE TABLE IF NOT EXISTS global_alerts
                    (id INTEGER PRIMARY KEY AUTOINCREMENT, 
                     timestamp TEXT, 
                     source TEXT, 
                     title TEXT, 
                     message TEXT)''')
    conn.commit()
    conn.close()

init_alerts_db()

# Słownik do trzymania procesów demonów w pamięci serwera
active_processes = {
    'polymarket': None,
    'binance': None
}

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/status')
def get_status():
    status = {
        'polymarket': active_processes['polymarket'] is not None and active_processes['polymarket'].poll() is None,
        'binance': active_processes['binance'] is not None and active_processes['binance'].poll() is None
    }
    return jsonify(status)

@app.route('/api/toggle', methods=['POST'])
def toggle_daemon():
    data = request.json
    daemon = data.get('daemon')
    action = data.get('action') # 'start' lub 'stop'

    if daemon not in active_processes:
        return jsonify({"error": "Unknown daemon"}), 400

    venv_python = os.path.join(BASE_DIR, ".venv", "bin", "python")
    script_map = {
        'polymarket': os.path.join(BASE_DIR, "src", "streamers", "polymarket_daemon.py"),
        'binance': os.path.join(BASE_DIR, "src", "streamers", "binance_oi_daemon.py")
    }

    if action == 'start':
        if active_processes[daemon] is None or active_processes[daemon].poll() is not None:
            # Uruchamiamy demona
            p = subprocess.Popen([venv_python, script_map[daemon]], cwd=BASE_DIR)
            active_processes[daemon] = p
            return jsonify({"status": "started", "daemon": daemon})
        return jsonify({"status": "already_running", "daemon": daemon})
        
    elif action == 'stop':
        p = active_processes[daemon]
        if p and p.poll() is None:
            p.terminate()
            active_processes[daemon] = None
            return jsonify({"status": "stopped", "daemon": daemon})
        return jsonify({"status": "not_running", "daemon": daemon})

@app.route('/api/alerts')
def get_alerts():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    # Pobieramy najnowsze 50 alertów
    alerts = conn.execute("SELECT * FROM global_alerts ORDER BY id DESC LIMIT 50").fetchall()
    conn.close()
    return jsonify([dict(a) for a in alerts])

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5050, debug=True)
