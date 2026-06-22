# AI-PresentEd Generation Service

> Микросервис генерации адаптивных образовательных презентаций.
> Часть дипломного проекта **AI-PresentEd** (ВКР).

---

## 📋 О проекте

**AI-PresentEd Generation Service** — это FastAPI-микросервис, который автоматически генерирует адаптивные учебные презентации. Является частью системы **AI-PresentEd**.

Возможности:
- 📊 Генерация структуры презентации (заголовки слайдов) по заданной теме
- 📝 Генерация содержимого каждого слайда (4-5 предложений на русском)
- 🎯 Адаптация текста под профиль ОВЗ (дислексия, СДВГ, слабовидение)
- 🖼️ Автоподбор иллюстраций из Wikipedia (en + ru)
- ♿ Генерация WCAG 2.2-совместимых alt-текстов для изображений
- 🔐 REST API с токенной аутентификацией

---

## 🏗️ Архитектура системы

```
┌──────────────────────────┐         ┌──────────────────────────────┐
│  AI-PresentEd            │         │ AI-PresentEd GenService       │
│  (Владислав Надеждин)    │  HTTP   │ (Денис Миркутов)              │
│                          │ ──────▶ │                              │
│  • Frontend              │  JSON   │  • Структура презентации     │
│  • Backend (Django/FastAPI)        │  • Контент слайдов            │
│  • БД пользователей      │ ◀────── │  • Подбор картинок           │
│  • Авторизация           │  JSON   │  • Генерация alt-текстов     │
└──────────────────────────┘         └──────────────────────────────┘
       Порт: 8000                              Порт: 8001
       (frontend: 3000)
```

**Распределение ответственности (команда из 2 человек):**

| Что | Кто | Репозиторий |
|---|---|---|
| AI-PresentEd (фронт + бэк + БД) | Надеждин Владислав | (отдельный репо) |
| AI-PresentEd GenService (этот) | Миркутов Денис | https://github.com/AXTAXALEN/AI-PresentEd-GenService |

Влад делает HTTP-запросы к нам по токену, мы отвечаем структурированным JSON'ом.

---

## ✨ Возможности

### Базовые
- Генерация структуры презентации по теме
- Генерация содержимого каждого слайда (4-5 предложений)
- Подбор иллюстраций из Wikipedia (английская + русская)
- WCAG 2.2-совместимые alt-тексты

### Профили адаптации ОВЗ

| Профиль | Особенности стиля |
|---|---|
| `dyslexia` | Прямой порядок слов, короткие предложения, выделение `<b>` |
| `adhd` | Короткие фрагменты, интригующие факты, динамичный стиль |
| `vision` | Экстремально краткий текст (для крупного шрифта при слабовидении) |
| `default` | Научно-популярный стиль, факты, даты |

### Тарифы (количество слайдов)

| Тариф | `slides_count` | По умолчанию |
|---|---|---|
| **Базовый** | 1-7 | 7 |
| **Pro** | 1-15 | до 15 |

Параметр `slides_count` принимается в запросе. Валидация `1..15` — на стороне микросервиса (Pydantic, статус `422` при нарушении). Решение, какой тариф у пользователя — на стороне основного сервиса (Влад).

---

## 🛠 Технологический стек

- **Python 3.10+**
- **FastAPI** — REST API
- **Pydantic v2** — валидация запросов/ответов
- **llama-cpp-python** — локальная LLM (Qwen 14B, Q4_K)
- **CUDA** (опционально) — GPU-ускорение LLM
- **requests** — HTTP к Wikipedia API
- **Pillow** — обработка изображений

---

## 📁 Структура проекта

```
gen-service/
├── main.py                       # Точка входа FastAPI, CORS, /health
├── config.py                     # Загрузка переменных окружения из .env
├── models.py                     # Pydantic-модели запросов/ответов
│                                 # (включая валидацию slides_count: 1..15)
├── routers/
│   └── generate.py               # POST /generate/structure, /generate/slides
├── services/
│   ├── ai.py                     # ★ Ядро: LLM-логика, структура, контент, alt-тексты
│   └── image_downloader.py       # Скачивание картинок с Wikipedia
├── rag_config.json               # Правила для профилей ОВЗ (role_modifier + rules)
├── requirements.txt              # Python-зависимости
├── run.sh                        # Скрипт запуска на Linux-сервере с GPU
├── .env.example                  # Шаблон переменных окружения
├── .gitignore                    # Исключения Git (секреты, модель, кэши)
└── README.md                     # Этот файл
```

---

## 🚀 Установка и запуск

### Системные требования

- **Python 3.10+**
- **8 ГБ RAM** минимум (16 ГБ рекомендуется)
- **CUDA-совместимая GPU** (опционально, для ускорения LLM)
- **~10 ГБ** свободного места для модели Qwen 14B (Q4_K-квантизация)

### Пошаговая установка

#### 1. Клонировать репозиторий

```bash
git clone https://github.com/AXTAXALEN/AI-PresentEd-GenService.git
cd AI-PresentEd-GenService
```

#### 2. Создать виртуальное окружение

**Linux / macOS:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

#### 3. Установить зависимости

```bash
pip install -r requirements.txt
```

> ⚠️ `llama-cpp-python` собирается долго (5-15 мин). Для GPU-ускорения установите CUDA Toolkit **до** `pip install`.

#### 4. Скачать модель Qwen 14B

Скачайте GGUF-файл с квантизацией Q4_K (~8-10 ГБ) и поместите в папку `models/` **с именем `model-q4_K.gguf`** (либо обновите `possible_paths` в `services/ai.py`).

Источник: репозиторий [Qwen](https://huggingface.co/Qwen) на HuggingFace — ищите сборку `*-GGUF` нужной версии (Qwen 1.5 / 2 / 2.5 / 3) и скачивайте файл `*-q4_K.gguf`.

#### 5. Настроить переменные окружения

```bash
cp .env.example .env
nano .env   # или любой редактор
```

Минимально необходимое в `.env`:
```bash
SERVICE_TOKEN=your-secret-token-here   # случайная длинная строка
PORT=8001
```

---

## ▶️ Запуск

### Режим разработки (на вашем ПК, без GPU)

```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8001
```

> Без модели сервис запустится с заглушкой (`DummyLLM`), который возвращает `"Модель временно недоступна."` Это удобно для разработки и отладки API.

### Продакшн (на Linux-сервере с GPU)

```bash
bash run.sh
```

Скрипт активирует venv, прописывает пути к NVIDIA-библиотекам и запускает `main.py`.

### Проверка работоспособности

```bash
curl http://localhost:8001/health
# Ответ: {"status":"ok"}
```

Swagger UI (интерактивная документация API): http://localhost:8001/docs

---

## 📡 API Reference

Все эндпоинты (кроме `/health` и `/docs`) требуют заголовок `X-Service-Token`.

### `GET /health`

Проверка работоспособности. Без аутентификации.

```bash
curl http://localhost:8001/health
# {"status":"ok"}
```

---

### `POST /generate/structure`

Генерация структуры презентации (заголовки слайдов).

**Запрос:**

```json
{
  "topic": "Квантовая физика",
  "profile": "default",
  "slides_count": 10
}
```

| Поле | Тип | Обязательно | Описание |
|---|---|---|---|
| `topic` | string | ✅ | Тема презентации (произвольный текст) |
| `profile` | string | ❌ | Профиль ОВЗ: `default` / `dyslexia` / `adhd` / `vision`. По умолчанию `default` |
| `slides_count` | int | ❌ | Кол-во слайдов: **1..15**. По умолчанию `7`. Pro-тариф использует `15` |

**Ответ:**

```json
{
  "title": "Квантовая физика: введение",
  "slides": [
    {"number": 1, "title": "История физики"},
    {"number": 2, "title": "Атомная модель"},
    {"number": 3, "title": "Фотоэффект"}
  ]
}
```

**Пример:**

```bash
curl -X POST http://localhost:8001/generate/structure \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: dev-token-123" \
  -d '{"topic": "Квантовая физика", "slides_count": 10}'
```

---

### `POST /generate/slides`

Генерация полного контента слайдов (текст + изображение + alt-текст).

**Запрос:**

```json
{
  "topic": "Квантовая физика",
  "profile": "default",
  "structure": [
    {"number": 1, "title": "История физики"},
    {"number": 2, "title": "Атомная модель"}
  ]
}
```

**Ответ:**

```json
{
  "slides": [
    {
      "number": 1,
      "title": "История физики",
      "content": "Квантовая физика зародилась в начале XX века. Макс Планк в 1900 году предложил идею квантов энергии. Альберт Эйнштейн в 1905 году объяснил фотоэффект. Эрвин Шрёдингер в 1926 году создал волновое уравнение.",
      "image_url": "https://upload.wikimedia.org/wikipedia/...",
      "image_alt": "Фотография Макса Планка, основоположника квантовой теории.",
      "image_prompt": "История физики"
    }
  ]
}
```

**Пример:**

```bash
curl -X POST http://localhost:8001/generate/slides \
  -H "Content-Type: application/json" \
  -H "X-Service-Token: dev-token-123" \
  -d '{
    "topic": "Квантовая физика",
    "structure": [
      {"number": 1, "title": "История физики"},
      {"number": 2, "title": "Атомная модель"}
    ]
  }'
```

---

### Коды ошибок

| Код | Когда |
|---|---|
| `200` | Успех |
| `401` | Невалидный или отсутствующий `X-Service-Token` |
| `422` | Невалидное тело запроса (например, `slides_count=20`) |
| `500` | Внутренняя ошибка (сбой LLM, таймаут и т.д.) |

---

## 🔗 Интеграция с основным сервисом AI-PresentEd

Этот микросервис — «бэкенд для бэкенда». Его вызывает основной сервис **AI-PresentEd** (Владислав Надеждин).

### Архитектура взаимодействия

```
[Frontend (React/Vue)]
        ↓ HTTPS
[AI-PresentEd Backend] ← порт 8000
        ↓ HTTP + X-Service-Token
[Этот микросервис] ← порт 8001
        ↓
[Qwen 14B + Wikipedia API]
```

### Контракт аутентификации

Бэкенд AI-PresentEd шлёт заголовок `X-Service-Token`. Значение должно **совпадать** с `SERVICE_TOKEN` в `.env` нашего микросервиса.

**Пример для бэкенда Влада (Python):**

```python
import httpx
import os

GEN_SERVICE_URL = "http://localhost:8001"  # или http://gen-service-host:8001
SERVICE_TOKEN = os.getenv("GEN_SERVICE_TOKEN")  # = наш SERVICE_TOKEN

async def generate_presentation(topic: str, slides_count: int, profile: str = "default"):
    headers = {"X-Service-Token": SERVICE_TOKEN}
    
    # 1. Получить структуру (быстро, ~3-5 сек)
    structure_resp = await httpx.post(
        f"{GEN_SERVICE_URL}/generate/structure",
        json={"topic": topic, "slides_count": slides_count, "profile": profile},
        headers=headers,
        timeout=60.0,
    )
    structure_resp.raise_for_status()
    structure = structure_resp.json()
    
    # 2. Получить полные слайды (долго, ~30-90 сек для 15 слайдов)
    slides_resp = await httpx.post(
        f"{GEN_SERVICE_URL}/generate/slides",
        json={
            "topic": topic,
            "profile": profile,
            "structure": structure["slides"],
        },
        headers=headers,
        timeout=300.0,  # 5 минут — с запасом
    )
    slides_resp.raise_for_status()
    return slides_resp.json()
```

### Рекомендуемые таймауты

| Эндпоинт | Среднее время | Рекомендуемый таймаут |
|---|---|---|
| `/generate/structure` (7 слайдов) | 3-5 сек | 60 сек |
| `/generate/structure` (15 слайдов) | 5-10 сек | 90 сек |
| `/generate/slides` (7 слайдов) | 20-40 сек | 180 сек |
| `/generate/slides` (15 слайдов) | 40-90 сек | 300 сек |

### Развёртывание в продакшне

Типичная схема на сервере:

```
Сервер (Linux + GPU)
├── /home/adminstudent/ai-presented/        ← Влад: основной сервис (порт 8000)
└── /home/adminstudent/projects/gen-service/ ← Денис: этот микросервис (порт 8001)
```

Оба сервиса работают на одной машине. Между собой общаются через `localhost:8001`. Для внешнего доступа — через Nginx на 8000.

---

## ⚙️ Конфигурация (.env)

| Переменная | Описание | По умолчанию |
|---|---|---|
| `SERVICE_TOKEN` | **Обязательно.** Токен для аутентификации запросов от основного сервиса | `dev-token-123` |
| `PORT` | Порт FastAPI | `8001` |
| `USE_YANDEX` | Использовать YandexGPT вместо локальной модели | `False` |
| `YC_FOLDER_ID` | Yandex Cloud folder ID (для YandexGPT) | `""` |
| `YC_API_KEY` | API-ключ Yandex Cloud | `""` |
| `UNSPLASH_ACCESS_KEY` | API-ключ Unsplash (для fallback-картинок) | `""` |

> 🔒 **Никогда не коммитьте `.env`** — он в `.gitignore`. Используйте `.env.example` как шаблон.

---

## 🐛 Решение проблем

### `МОДЕЛЬ НЕ НАЙДЕНА! Используется заглушка.`

Проверьте:
1. Файл `models/model-q4_K.gguf` существует.
2. Путь в `services/ai.py` (`possible_paths`) соответствует вашему расположению.

### Out of memory при загрузке модели

- Закройте другие приложения, использующие GPU.
- Используйте меньшую квантизацию модели (`Q3_K` вместо `Q4_K`).
- Уменьшите `n_ctx` в `services/ai.py` (по умолчанию 4096).

### LLM возвращает мусор вместо JSON

- Увеличьте `max_tokens` (может обрезаться ответ на полуслове).
- Понизьте `temperature` (по умолчанию 0.2-0.3).
- Используйте более точную модель (Q5_K или Q8_K).

### Картинки не находятся в Wikipedia

Это нормально для узких тем. Сервис делает fallback на `FALLBACK_IMAGES` (5 заглушек из Unsplash). Логи покажут, какие ключевые слова не дали результата.

### Push в GitHub: `Host key verification failed`

Сгенерируйте SSH-ключ и добавьте его в GitHub:
```bash
ssh-keygen -t ed25519
cat ~/.ssh/id_ed25519.pub   # скопируйте → https://github.com/settings/keys
ssh -T git@github.com       # проверить
```

---

## 👥 Команда

| Роль | Ответственность | GitHub |
|---|---|---|
| **Миркутов Денис** | Этот микросервис: ИИ-логика, генерация, изображения | `AXTAXALEN` |
| **Надеждин Владислав** | Основной сервис AI-PresentEd: фронтенд, бэкенд, БД | (отдельный аккаунт) |

**Дипломная работа**, ВКР, Воронежский государственный технический университет (ВГТУ), 2026.

---

## 📄 Лицензия

MIT License. Свободное использование с указанием авторства.
