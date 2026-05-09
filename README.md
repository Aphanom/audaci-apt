<div align="center">
  <img src="https://raw.githubusercontent.com/Aphanom/audaci-apt/main/assets/icon.png" width="120" alt="Audaci Logo">
  <h1>Audaci Music Player</h1>
  <p><b>Интеллектуальный плеер для Astra Linux: AI-диджей, Голос и Караоке</b></p>

  <img src="https://img.shields.io/badge/Python-3.11+-blue.svg?style=for-the-badge&logo=python&logoColor=white">
  <img src="https://img.shields.io/badge/Flet-0.84-00A8E8.svg?style=for-the-badge&logo=flutter&logoColor=white">
  <img src="https://img.shields.io/badge/Astra_Linux-1.8-E3000F.svg?style=for-the-badge&logo=linux&logoColor=white">
</div>

---

## 🌟 Почему Audaci?
**Audaci** — это не просто плеер, а технологический эксперимент по созданию идеального аудио-окружения в системе Astra Linux. 

### ⚡ Основные фишки:
* 🤖 **AI-DJ**: Умный поиск по настроениям (Меланхолия, Драйв, Релаксация).
* 🎙 **Voice Control**: Полное оффлайн-управление голосом через Vosk.
* 📜 **Dynamic Lyrics**: Синхронизированные тексты песен в режиме "Фокус".
* 🛡 **Astra Native**: Полная поддержка безопасности PARSEC и интерфейса Fly.

---

## 📦 Быстрая установка (Astra Linux / Debian)
Скачайте и установите плеер прямо из терминала. APT автоматически подтянет все нужные системные зависимости (включая VLC).

\`\`\`bash
# 1. Скачиваем стабильную версию
wget https://github.com/Aphanom/audaci-apt/releases/download/v1.0/audaci_1.0-1_amd64.deb

# 2. Устанавливаем пакет
sudo apt install ./audaci_1.0-1_amd64.deb
\`\`\`
*(После установки ярлык Audaci появится в системном меню "Мультимедиа").*

---

## 🛠 Разработка (Запуск из исходников)
Если вы хотите изучить код или запустить плеер без установки:

1. **Клонируйте репозиторий:**
   \`\`\`bash
   git clone https://github.com/Aphanom/audaci-apt.git
   cd audaci-apt
   \`\`\`

2. **Настройте окружение:**
   \`\`\`bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   \`\`\`

3. **Голосовой движок:**
   * Скачайте компактную модель распознавания речи с [официального сайта Vosk](https://alphacephei.com/vosk/models) (рекомендуется `vosk-model-small-ru`).
   * Распакуйте папку и переименуйте её в `model`, поместив в корень проекта.

4. **Запуск:**
   \`\`\`bash
   python3 main.py
   \`\`\`

---
<div align="center">
  <i>Разработано @Aphanom. Проект находится в активной стадии развития.</i>
</div>
