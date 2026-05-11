#!/bin/bash

echo "🚀 Rozpoczynamy publikację na GitHubie..."

# 1. Zmiana nazwy starego origin i dodanie nowego
git remote rename origin stare-repo 2>/dev/null
git remote add origin https://github.com/TedeuszNorek/Crisis_Preventer.git 2>/dev/null || git remote set-url origin https://github.com/TedeuszNorek/Crisis_Preventer.git

# 2. Dodajemy zmiany (w tym nowe README)
git add .
git commit -m "feat: Crisis Preventer Quant Engine - initial commit"

# 3. Próba połączenia historii, jeśli repozytorium nie było puste
echo "⬇️ Pobieranie danych z Crisis_Preventer..."
git fetch origin

if [ $? -eq 0 ]; then
    echo "🔀 Łączenie historii..."
    git merge origin/main --allow-unrelated-histories -m "Merge: Crisis Preventer fuzja"
fi

# 4. Wysyłka
echo "⬆️ Wysyłanie kodu na serwer..."
git push -u origin main

if [ $? -eq 0 ]; then
    echo "✅ Sukces! Kod jest już na GitHubie!"
else
    echo "❌ Wystąpił błąd podczas wysyłania. Upewnij się, że masz skonfigurowane hasło/token na swoim komputerze."
fi
