import subprocess
import re
import time
import os

# 1. Kill old processes (bez psutil)
os.system("pkill -f telegram_entry.py 2>/dev/null")
os.system("pkill -f cloudflared 2>/dev/null")
time.sleep(1)

print("Uruchamianie tunelu Cloudflare (Szybki i BEZ ekranów blokujących)...")

# Try to run cloudflared. It sends logs to stderr.
proc = subprocess.Popen(
    ["/opt/homebrew/bin/cloudflared", "tunnel", "--url", "http://127.0.0.1:8003"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

url = None
# We wait for the trycloudflare.com url to appear in the output.
start_time = time.time()
while time.time() - start_time < 15:
    line = proc.stdout.readline()
    if not line:
        time.sleep(0.1)
        continue
    
    match = re.search(r'(https://[a-zA-Z0-9-]+\.trycloudflare\.com)', line)
    if match:
        url = match.group(1)
        break

if url:
    print(f"\n+++ SUKCES! Złapano czysty URL Cloudflare: {url} +++\n")
    with open("url.txt", "w") as f: f.write(url)
    bot_file = os.path.join(os.path.dirname(__file__), "telegram_entry.py")
    with open(bot_file, "r") as f:
        content = f.read()
        
    content = re.sub(r'WEB_APP_URL\s*=\s*".*?"', f'WEB_APP_URL = "{url}"', content)
    
    with open(bot_file, "w") as f:
        f.write(content)
    
    # Używamy Pythona z venva (ma zainstalowane python-telegram-bot)
    venv_python = os.path.join(os.path.dirname(__file__), '..', '..', '.venv', 'bin', 'python3')
    venv_python = os.path.abspath(venv_python)
    
    print("Odpalam połączonego Bota na nowym URL z Cloudflare...")
    os.system(f"nohup {venv_python} {bot_file} >> tunnel.log 2>&1 &")
else:
    print("Nie udało się znaleźć URL od Cloudflare.")
    proc.kill()
