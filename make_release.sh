#!/bin/bash

# Цвета
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${BLUE}=== Запуск автоматической сборки и публикации Audaci ===${NC}"

# Запрашиваем текст коммита до начала долгой сборки
echo -e "${YELLOW}Введите описание изменений для GitHub (или нажми Enter для '🚀 Update Audaci'):${NC}"
read COMMIT_MSG
if [ -z "$COMMIT_MSG" ]; then
    COMMIT_MSG="🚀 Update Audaci"
fi

# 1. Очистка старых хвостов
echo -e "${BLUE}1. Очистка временных файлов...${NC}"
rm -rf build/ dist/

# 2. Сборка бинарника
echo -e "${BLUE}2. Сборка исполняемого файла...${NC}"
pyinstaller --noconfirm audaci.spec

if [ $? -eq 0 ]; then
    echo -e "${GREEN}✔ Бинарник успешно собран!${NC}"
else
    echo "❌ Ошибка при сборке PyInstaller"
    exit 1
fi

# 3. Обновление структуры .deb
echo -e "${BLUE}3. Упаковка в .deb структуру...${NC}"
cp dist/audaci build_deb/audaci_1.0-1_amd64/opt/audaci/audaci

# 4. Сборка пакета
echo -e "${BLUE}4. Финальная сборка пакета dpkg...${NC}"
dpkg-deb --build build_deb/audaci_1.0-1_amd64

# 5. Синхронизация кода с GitHub
echo -e "${BLUE}5. Отправка исходного кода на GitHub...${NC}"
cp main.py ~/audaci-apt/
cd ~/audaci-apt || exit
git add .
git commit -m "$COMMIT_MSG"
git push

# Возвращаемся в исходную папку
cd - > /dev/null

echo -e "${GREEN}=== РЕЛИЗ УСПЕШНО ЗАВЕРШЕН ===${NC}"
echo -e "📦 Пакет лежит здесь: build_deb/audaci_1.0-1_amd64.deb"
echo -e "🐙 Код отправлен на GitHub!"
