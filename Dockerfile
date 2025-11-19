FROM python:3.12-slim

# Установка системных зависимостей
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Создание пользователя приложения
RUN groupadd --gid 2000 app && \
    useradd --uid 2000 --gid 2000 -m -d /app app

# Установка рабочей директории
WORKDIR /app

# Копирование файлов зависимостей
COPY requirements.txt .

# Установка Python зависимостей
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Копирование всех файлов проекта
COPY --chown=app:app . .

# Переключение на пользователя приложения
USER app

# Открытие порта
EXPOSE 8000

# Команда запуска
CMD ["bash", "start.sh"]

