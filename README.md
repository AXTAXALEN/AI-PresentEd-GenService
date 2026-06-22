# AI-PresentEd Generation Service

Микросервис для генерации адаптивных образовательных презентаций с использованием AI.

## Возможности

- Генерация структуры презентаций (тема → список слайдов)
- Генерация контента слайдов с адаптацией под профили ОВЗ
- Поддержка локальных моделей (Saiga Llama 3) и облачных (YandexGPT)
- Автоматический поиск и загрузка изображений

## Требования

- Python 3.10+
- CUDA-совместимая GPU (для локальной генерации)
- 8+ GB RAM (16 GB рекомендуется)

## Установка

1. Клонируйте репозиторий:
   ```bash
   git clone https://github.com/YOUR_USERNAME/AI-PresentEd-GenService.git
   cd AI-PresentEd-GenService
   ```

2. Создайте виртуальное окружение:
    ```bash
    python -m venv .venv
    .venv\Scripts\activate  # Windows
    source .venv/bin/activate  # Linux/Mac
    ```

3. Установите зависимости:
    ```bash
   pip install -r requirements.txt
    ```

4. Скопируйте .env.example в .env и настройте переменные:
    ```bash
   cp .env.example .env
    ```

5. Поместите модель model-q4_K.gguf в папку models/.

## Запуск

Запустите сервис через команду:
```bash
python main.py
```

Сервис будет доступен по адресу: http://localhost:8001

## Конфигурация

Переменные окружения (.env):
```bash
SERVICE_TOKEN=your-secret-token
PORT=8001
USE_YANDEX=False
YC_FOLDER_ID=your-folder-id
YC_API_KEY=your-api-key
```

## Лицензия

MIT License.
