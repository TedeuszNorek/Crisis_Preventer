import os
import psutil
from pyngrok import ngrok
import re
import time

# 1. Kill existing bot processes to avoid conflict with Telegram Bot API token
current_pid = os.getpid()
for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
    try:
        cmdline = proc.info.get('cmdline')
        if cmdline and 'telegram_entry.py' in ' '.join(cmdline):
            if proc.info['pid'] != current_pid:
                print(f"Killing old bot process: {proc.info['pid']}")
                proc.kill()
    except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
        pass

# 2. Start Ngrok tunnel for port 8000
try:
    print("Otwieranie szyfrowanego tunelu Ngrok dla portu 8000...")
    public_url = ngrok.connect(8000).public_url
    public_url = public_url.replace("http://", "https://")
    print(f"Sukces! Nowy tunel to: {public_url}")
except Exception as e:
    print(f"Failed to start ngrok: {e}")
    exit(1)

# 3. Patch the telegram_entry.py file with the new URL
bot_file = os.path.join(os.path.dirname(__file__), "telegram_entry.py")
with open(bot_file, "r") as f:
    content = f.read()

# Replace any existing WEB_APP_URL with the fresh ngrok URL
content = re.sub(r'WEB_APP_URL\s*=\s*".*?"', f'WEB_APP_URL = "{public_url}"', content)

with open(bot_file, "w") as f:
    f.write(content)
print("Zaktualizowano telegram_entry.py automatycznie.")

# 4. Import and run the bot
print("Przekazywanie kontroli do Bota... Możesz testować w aplikacji!")
import telegram_entry
telegram_entry.main()
