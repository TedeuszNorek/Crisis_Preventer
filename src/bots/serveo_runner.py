import subprocess
import re
import time
import os
import psutil

# Zabij stare procesy bota
current_pid = os.getpid()
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.info.get('cmdline')
        if cmdline and ('telegram_entry.py' in ' '.join(cmdline) or 'pinggy' in ' '.join(cmdline)):
            if proc.info['pid'] != current_pid:
                proc.kill()
    except:
        pass

print("Inicjowanie chmurowego tunelu Serveo...")
proc = subprocess.Popen(
    ["ssh", "-o", "StrictHostKeyChecking=no", "-R", "80:localhost:8000", "serveo.net"],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True
)

url = None
# Czekamy maksymalnie na 15 linii logów
for _ in range(15):
    line = proc.stdout.readline()
    if not line: break
    print(f"Tunel: {line.strip()}")
    match = re.search(r'Forwarding (?:HTTP|HTTPS) traffic from (https://[^\s]+)', line)
    if match:
        url = match.group(1)
        break

if url:
    print(f"\n+++ SUKCES! Podpinam tunel do Bota: {url} +++\n")
    bot_file = os.path.join(os.path.dirname(__file__), "telegram_entry.py")
    with open(bot_file, "r") as f:
        content = f.read()
        
    content = re.sub(r'WEB_APP_URL\s*=\s*".*?"', f'WEB_APP_URL = "{url}"', content)
    
    with open(bot_file, "w") as f:
        f.write(content)
        
    print("Odpalanie połączonego Bota...")
    import telegram_entry
    telegram_entry.main()
else:
    print("Nie udało się zbudować cichego tunelu. Możliwe blokady firewall portu 22.")
