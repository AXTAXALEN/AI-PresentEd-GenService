import json, os, re, time, requests, random
from llama_cpp import Llama
from config import USE_YANDEX, YC_FOLDER_ID, YC_API_KEY, GLOBAL_MEDIA_PATH

session = requests.Session()
HEADERS = {
    'User-Agent': 'AI-PresentEd-SuperFinal/9.5 (student@vstu.ru)'
}

_llm = None
BANNED_TOPICS_REGEX = r"(лгбт|lgbt|геи|лесбиянки|трансгендеры|наркотики|суицид|экстремизм|паркур|экология|экологические)"

# ─────────────────────────────────────────────
# Вспомогательные функции
# ─────────────────────────────────────────────

def smart_truncate(text, max_length=380):
    if not text:
        return ""
    if len(text) <= max_length:
        return text
    truncated = text[:max_length]
    last_punc = max(truncated.rfind('.'), truncated.rfind('!'), truncated.rfind('?'))
    if last_punc > 100:
        return truncated[:last_punc + 1]
    last_space = truncated.rfind(' ')
    return truncated[:last_space] + "." if last_space > 0 else truncated + "."


def clean_text(text_data):
    if not text_data:
        return ""
    if isinstance(text_data, list):
        text = " ".join(
            [str(i.get('text', i)) if isinstance(i, dict) else str(i) for i in text_data]
        )
    else:
        text = str(text_data)
    text = re.sub(r'"(text|content|prompt|result)":', '', text, flags=re.IGNORECASE)
    if re.search(BANNED_TOPICS_REGEX, text, flags=re.IGNORECASE):
        return "Материал адаптирован под образовательные стандарты."
    return " ".join(text.strip("[]'\" ").split())


def clean_json_response(text):
    """
    Попытка 1: прямой парсинг JSON-блока.
    Попытка 2: поиск первого {...} с любым количеством вложенных символов.
    Попытка 3: поиск первого {...} через нежадный поиск.
    """
    if not text:
        return None
    # Убираем markdown-обёртки
    cleaned = re.sub(r'```(?:json)?\s*|\s*```', '', text).strip()

    for pattern in [r'\{[^{}]*\}', r'\{.*?\}', r'\{.*\}']:
        match = re.search(pattern, cleaned, re.DOTALL)
        if match:
            candidate = match.group(0).replace('\n', ' ').replace('\r', ' ')
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                # Пробуем починить незакрытые строки
                try:
                    fixed = candidate.rstrip().rstrip(',') + '}'
                    return json.loads(fixed)
                except Exception:
                    continue
    return None


def extract_alt_from_raw(raw: str) -> str:
    """
    Агрессивный fallback-экстрактор для случаев, когда LLM не вернул
    корректный JSON, но всё же написал что-то полезное.

    Стратегии (в порядке приоритета):
      1. Ищем значение после "alt": или "alt" :
      2. Берём первое предложение, которое выглядит как описание (> 20 символов)
      3. Возвращаем None — вызывающий код подставит fallback
    """
    # Стратегия 1: вытащить значение ключа alt из не-JSON текста
    alt_match = re.search(
        r'"alt"\s*:\s*"([^"]{10,})"',
        raw, re.IGNORECASE
    )
    if alt_match:
        return alt_match.group(1).strip()

    # Стратегия 2: первое предложение, похожее на описание
    sentences = re.split(r'(?<=[.!?])\s+', raw.strip())
    for sent in sentences:
        sent_clean = sent.strip().strip('"\'').strip()
        # Отбрасываем JSON-артефакты и слишком короткие фразы
        if (
            len(sent_clean) >= 20
            and not sent_clean.startswith('{')
            and not sent_clean.startswith('[')
            and not re.match(r'^["\']?\s*\{', sent_clean)
        ):
            return sent_clean

    return ""


# ─────────────────────────────────────────────
# Локальная LLM
# ─────────────────────────────────────────────

def get_llm():
    global _llm
    if _llm is None:
        possible_paths = [
            "/home/adminstudent/projects/gen-service/models/model-q4_K.gguf",
            "/home/adminstudent/models/model-q4_K.gguf",
            "models/model-q4_K.gguf",
            "../models/model-q4_K.gguf"
        ]
        model_path = None
        for path in possible_paths:
            if os.path.exists(path):
                model_path = path
                break
        if not model_path:
            print("⚠️ МОДЕЛЬ НЕ НАЙДЕНА! Используется заглушка.")
            class DummyLLM:
                def create_chat_completion(self, *args, **kwargs):
                    return {"choices": [{"message": {"content": "{\"content\": \"Модель временно недоступна.\"}"}}]}
            _llm = DummyLLM()
            return _llm
        print(f"📦 Загружаем модель: {model_path}")
        _llm = Llama(model_path=model_path, n_ctx=4096, n_gpu_layers=-1, verbose=False)
    return _llm


def generate_text(sys_p, user_p, max_tokens=450, temp=0.2):
    llm = get_llm()
    res = llm.create_chat_completion(
        messages=[
            {"role": "system", "content": sys_p},
            {"role": "user", "content": user_p}
        ],
        max_tokens=max_tokens,
        temperature=temp
    )
    return res["choices"][0]["message"]["content"]


# ─────────────────────────────────────────────
# Генерация alt-текста
# ─────────────────────────────────────────────

# Минимальная длина, при которой alt считается осмысленным
_ALT_MIN_LEN = 20

# Максимальные длины alt по профилям (в символах)
_ALT_MAX_LEN = {
    "vision":   140,
    "dyslexia":  90,
    "adhd":     100,
    "default":  120,
}

def generate_image_alt(
    topic: str,
    slide_title: str,
    profile: str,
    slide_content: str = "",   # ← НОВЫЙ параметр: уже готовый текст слайда
    image_url: str = "",
) -> str:
    """
    Генерирует alt-текст для изображения слайда.

    Принципиальное изменение архитектуры:
    - Раньше: LLM пытался «понять» картинку по URL (невозможно — модель
      не скачивает URL).
    - Теперь: LLM описывает НАЗНАЧЕНИЕ изображения в контексте слайда,
      используя topic + slide_title + slide_content. Это соответствует
      WCAG 2.2 §1.1.1: alt должен передавать функцию изображения,
      а не его пиксельное содержимое.

    Параметр image_url сохранён для совместимости, но больше не передаётся
    в промпт — это устраняло бы «мусор» из хэшей файловых имён Wikimedia.
    """
    max_len = _ALT_MAX_LEN.get(profile, _ALT_MAX_LEN["default"])

    # Профиль-специфичные инструкции для LLM
    profile_rules = {
        "vision": (
            f"Пиши подробное описание для слабовидящих. "
            f"Начинай с «На изображении:». "
            f"Опиши главный объект, контекст и ключевые детали. "
            f"Не более {max_len} символов."
        ),
        "dyslexia": (
            f"Пиши очень просто: короткие слова, прямой порядок. "
            f"Одно предложение. Начинай с главного объекта или действия. "
            f"Не более {max_len} символов."
        ),
        "adhd": (
            f"Пиши живо и конкретно. Начинай с самого интересного факта. "
            f"Одно-два предложения. Не более {max_len} символов."
        ),
        "default": (
            f"Пиши информативно. Начни со слов «Фотография показывает» или «Изображение иллюстрирует». "
            f"Одно-два предложения. Не более {max_len} символов."
        ),
    }
    rule = profile_rules.get(profile, profile_rules["default"])

    # Берём первое предложение контента как дополнительный контекст,
    # чтобы LLM понял конкретику слайда, а не просто повторял заголовок
    content_hint = ""
    if slide_content:
        first_sentence_match = re.search(r'[^.!?]{10,}[.!?]', slide_content)
        if first_sentence_match:
            content_hint = first_sentence_match.group(0).strip()

    sys_p = (
        "Ты — специалист по веб-доступности (WCAG 2.2, критерий 1.1.1). "
        "Твоя задача — написать alt-текст для изображения учебной презентации на русском языке.\n\n"
        "ВАЖНО: ты НЕ видишь само изображение. Изображение подобрано как иллюстрация "
        "к слайду. Твоя цель — описать, что ДОЛЖНО быть на иллюстрации к данному слайду, "
        "чтобы незрячий или слабовидящий пользователь понял контекст.\n\n"
        f"Правила стиля: {rule}\n\n"
        "Ответь СТРОГО в формате JSON: "
        "{\"alt\": \"текст описания\"}\n"
        "Никакого другого текста вне JSON."
    )

    # Формируем user-промпт с максимальным контекстом
    parts = [
        f"Тема презентации: «{topic}».",
        f"Заголовок слайда: «{slide_title}».",
    ]
    if content_hint:
        parts.append(f"Первое предложение слайда: «{content_hint}».")
    parts.append(
        "Напиши alt-текст для иллюстративного изображения к этому слайду."
    )
    user_p = "\n".join(parts)

    # --- Попытка 1: запрос к LLM ---
    try:
        raw = generate_text(sys_p, user_p, max_tokens=200, temp=0.15)
    except Exception as e:
        print(f"⚠️ generate_image_alt: ошибка LLM: {e}")
        raw = ""

    # --- Попытка 2: парсим JSON ---
    alt = ""
    if raw:
        parsed = clean_json_response(raw)
        if parsed and isinstance(parsed, dict):
            alt = parsed.get("alt", "")

        # --- Попытка 3: агрессивный fallback-экстрактор ---
        if not alt or len(alt.strip()) < _ALT_MIN_LEN:
            alt = extract_alt_from_raw(raw)

    # Финальная очистка
    if alt:
        # Убираем обрамляющие кавычки (все виды, рекурсивно)
        alt = alt.strip()
        while alt and alt[0] in ('"', "'", "«") and alt[-1] in ('"', "'", "»"):
            alt = alt[1:-1].strip()
        # Обрезаем до лимита профиля, не разрывая слово
        if len(alt) > max_len:
            alt = smart_truncate(alt, max_length=max_len)

    # --- Финальный детерминированный fallback ---
    # Срабатывает если LLM ничего не дал или дал слишком мало
    if not alt or len(alt) < _ALT_MIN_LEN:
        fallbacks_by_profile = {
            "vision": (
                f"На изображении: иллюстрация к слайду «{slide_title}» "
                f"по теме «{topic}»."
            ),
            "dyslexia": (
                f"Картинка про {slide_title.lower()}."
            ),
            "adhd": (
                f"Фото по теме: {slide_title}."
            ),
            "default": (
                f"Фотография иллюстрирует тему «{slide_title}» "
                f"в контексте презентации «{topic}»."
            ),
        }
        alt = fallbacks_by_profile.get(profile, fallbacks_by_profile["default"])

    return alt


# ─────────────────────────────────────────────
# Генерация ключевых слов для поиска изображений
# ─────────────────────────────────────────────

def generate_search_keywords(topic: str, en_topic: str = "") -> list:
    base = en_topic if en_topic else topic
    sys_p = (
        "You are a Wikipedia search expert. "
        "Given a topic (person, animal, place, event, or concept), output EXACTLY 10 English "
        "search queries that are likely to match real Wikipedia article titles about the topic. "
        "Rules:\n"
        "- Each query must be 1-4 words.\n"
        "- Every query must be DIRECTLY and SPECIFICALLY about the given topic itself.\n"
        "- For animals/species: use the animal name + specific subtopic "
        "(breeds, behavior, anatomy, diet, senses, lifespan, etc.).\n"
        "- For people: use full name, albums, awards, tours, collaborators, record label.\n"
        "- For places/buildings: use the place name + architecture, history, construction, etc.\n"
        "- For concepts/events: use specific related articles, not general academic fields.\n"
        "- Do NOT use general academic disciplines unrelated to the topic.\n"
        "- Do NOT use generic visual descriptions (hair, eyes, outfit, style, fashion).\n"
        "- Do NOT use abstract or broad phrases.\n"
        "Return ONLY a JSON array of strings, nothing else. "
        "Example: [\"term one\", \"term two\", ...]"
    )
    user_p = f"Topic: {base}"

    raw = generate_text(sys_p, user_p, max_tokens=200, temp=0.3)

    keywords = []
    try:
        match = re.search(r'\[.*?\]', raw, re.DOTALL)
        if match:
            keywords = json.loads(match.group(0))
    except Exception:
        pass

    if not keywords or not isinstance(keywords, list):
        keywords = [k.strip().strip('"\'') for k in re.split(r'[,\n]', raw) if k.strip()]

    keywords = [
        re.sub(r'[^a-zA-Z0-9\s\-]', '', str(k)).strip()
        for k in keywords
        if k and isinstance(k, str)
    ]
    keywords = [k for k in keywords if 2 < len(k) <= 60]
    keywords = keywords[:10]

    if len(keywords) < 5:
        sys_fallback = "Translate the following topic to English (1-3 words). Return ONLY the translation."
        en_fallback = generate_text(sys_fallback, topic, max_tokens=20, temp=0.1).strip()
        en_fallback = re.sub(r'[^a-zA-Z0-9\s\-]', '', en_fallback).strip()
        if en_fallback:
            keywords = [en_fallback] + keywords

    return keywords


# ─────────────────────────────────────────────
# Константы и фильтры для изображений
# ─────────────────────────────────────────────

WIKI_API = "https://en.wikipedia.org/w/api.php"
RU_WIKI_API = "https://ru.wikipedia.org/w/api.php"

ALLOWED_EXTENSIONS = ('jpg', 'jpeg', 'png', 'webp')

BANNED_NAME_FRAGMENTS = [
    'flag_of', 'coat_of_arms', 'emblem_of', 'logo', 'icon',
    'locator_map', 'location_map', 'blank_map', 'signature',
    'commons-logo', 'wikidata-logo', 'wikimedia-logo',
    'transparent', 'diagram', 'chart', 'map', 'screenshot',
    'graph', 'symbol', 'template', 'banner', 'button',
    'coa_', 'ambox', 'wikisource', 'wikispecies', 'wikiquote',
    'wiktionary', 'wikivoyage',
]

BANNED_URL_FRAGMENTS = [
    'Flag_of', 'Coat_of_arms', 'Emblem_of',
    'Commons-logo', 'Wikidata-logo',
]

BANNED_ARTICLE_KEYWORDS = [
    'fighting', 'warfare', 'war crime', 'abu ghraib',
    'prison', 'torture', 'abuse', 'scandal',
    'video game', 'manga', 'anime', 'comic', 'comics',
    'tv series', 'episode', 'cartoon', 'animated', 'fictional',
    'pornography', 'erotic', 'nude', 'nudity', 'fetish',
    'roleplay', 'sexual',
    'list of flags', 'heraldry',
    'musical', 'theatre', 'theater', 'broadway', 'opera', 'ballet',
    'stage production', 'west end',
    'disambiguation',
    "gray's anatomy", 'human anatomy',
]


def file_title_is_ok(title: str) -> bool:
    t = title.lower()
    if not any(t.endswith('.' + ext) for ext in ALLOWED_EXTENSIONS):
        return False
    for frag in BANNED_NAME_FRAGMENTS:
        if frag in t:
            return False
    return True


def url_is_ok(url: str) -> bool:
    u = url.lower()
    for frag in BANNED_URL_FRAGMENTS:
        if frag.lower() in u:
            return False
    return True


def tokenize(s: str) -> list:
    return [w.lower() for w in re.split(r'[\s\(\)\-*,\.\'\"]+', s) if len(w) > 1]


def normalize_token(w: str) -> str:
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


def token_set(s: str) -> set:
    return {normalize_token(t) for t in tokenize(s)}


def article_is_relevant_to_query(article_title: str, query: str) -> bool:
    title_lower = article_title.lower()
    for banned in BANNED_ARTICLE_KEYWORDS:
        if banned in title_lower:
            return False
    query_tokens = [t for t in tokenize(query) if len(t) > 2]
    if not query_tokens:
        return True
    title_norms = token_set(article_title)
    for tok in query_tokens:
        tok_norm = normalize_token(tok)
        if tok_norm in title_norms:
            return True
        if len(tok_norm) >= 4 and tok_norm[:4] in title_lower:
            return True
    return False


def filename_is_relevant_to_topic(file_title: str, topic_tokens: set) -> bool:
    if not topic_tokens:
        return True
    name = re.sub(r'^File:', '', file_title, flags=re.IGNORECASE)
    name = re.sub(r'\.[^.]+$', '', name)
    file_norms = token_set(name)
    return bool(topic_tokens & file_norms)


def build_topic_tokens(en_topic: str, keywords: list) -> set:
    tokens = set()
    for source in [en_topic] + keywords:
        for tok in tokenize(source):
            if len(tok) > 2:
                tokens.add(normalize_token(tok))
    return tokens


# ─────────────────────────────────────────────
# Получение изображений из Wikipedia
# ─────────────────────────────────────────────

def get_images_for_article(api_url, article_title, seen_urls, max_images=3, topic_tokens=None):
    found = []
    try:
        r1 = session.get(api_url, params={
            "action": "query", "format": "json",
            "titles": article_title, "prop": "images", "imlimit": 50,
        }, headers=HEADERS, timeout=8)
        r1.raise_for_status()
        data1 = r1.json()
    except Exception:
        return found

    pages = data1.get("query", {}).get("pages", {})
    file_titles = []
    for page_data in pages.values():
        for img in page_data.get("images", []):
            title = img.get("title", "")
            if not file_title_is_ok(title):
                continue
            if topic_tokens is not None and not filename_is_relevant_to_topic(title, topic_tokens):
                continue
            file_titles.append(title)

    if not file_titles:
        return found

    batch_size = 20
    for batch_start in range(0, min(len(file_titles), 60), batch_size):
        batch = file_titles[batch_start:batch_start + batch_size]
        try:
            r2 = session.get(api_url, params={
                "action": "query", "format": "json",
                "titles": "|".join(batch),
                "prop": "imageinfo", "iiprop": "url|size", "iiurlwidth": 1200,
            }, headers=HEADERS, timeout=8)
            r2.raise_for_status()
            data2 = r2.json()
        except Exception:
            continue

        batch_pages = data2.get("query", {}).get("pages", {})
        for pid, page_data in batch_pages.items():
            imageinfo_list = page_data.get("imageinfo", [])
            if not imageinfo_list:
                continue
            info = imageinfo_list[0]
            url = info.get("thumburl") or info.get("url", "")
            if not url:
                continue
            thumb_w = info.get("thumbwidth") or info.get("width") or 0
            if thumb_w and thumb_w < 300:
                continue
            if url in seen_urls:
                continue
            if not url_is_ok(url):
                continue
            seen_urls.add(url)
            found.append(url)
            if len(found) >= max_images:
                return found

    return found


def search_wiki_and_collect(api_url, query, seen_urls, max_per_kw=2, topic="", topic_tokens=None):
    collected = []
    try:
        r = session.get(api_url, params={
            "action": "query", "list": "search", "srsearch": query,
            "format": "json", "srlimit": 5, "srnamespace": 0,
        }, headers=HEADERS, timeout=8)
        r.raise_for_status()
        results = r.json().get("query", {}).get("search", [])
    except Exception:
        return collected

    for result in results:
        title = result.get("title", "")
        if not title:
            continue
        if not article_is_relevant_to_query(title, query):
            continue
        imgs = get_images_for_article(
            api_url, title, seen_urls,
            max_images=max_per_kw,
            topic_tokens=topic_tokens,
        )
        collected.extend(imgs)
        if len(collected) >= max_per_kw * 2:
            break

    return collected


def singularize(word: str) -> str:
    w = word.strip()
    if len(w) > 3 and w.endswith('s') and not w.endswith('ss'):
        return w[:-1]
    return w


# ─────────────────────────────────────────────
# Основная функция сбора пула изображений
# ─────────────────────────────────────────────

def get_smart_image_pool(topic: str) -> list:
    sys_direct = (
        "Translate the following topic to English (1-5 words). "
        "Return ONLY the translation, no punctuation."
    )
    en_topic = generate_text(sys_direct, topic, max_tokens=30, temp=0.1).strip()
    en_topic = re.sub(r'[^a-zA-Z0-9\s\-]', '', en_topic).strip()

    keywords = generate_search_keywords(topic, en_topic=en_topic)
    topic_tokens = build_topic_tokens(en_topic, keywords)

    priority_pool = []
    extra_pool = []
    seen_urls = set()

    if en_topic:
        words = en_topic.split()
        singular_last = singularize(words[-1])
        candidates = [en_topic]
        if singular_last != words[-1]:
            singular_topic = ' '.join(words[:-1] + [singular_last]) if len(words) > 1 else singular_last
            if singular_topic != en_topic:
                candidates.append(singular_topic)

        direct_found = False
        for candidate in candidates:
            direct_imgs = get_images_for_article(
                WIKI_API, candidate, seen_urls,
                max_images=7, topic_tokens=topic_tokens,
            )
            if direct_imgs:
                priority_pool.extend(direct_imgs)
                direct_found = True
                break

        if not direct_found:
            direct_search = search_wiki_and_collect(
                WIKI_API, en_topic, seen_urls,
                max_per_kw=5, topic=en_topic, topic_tokens=topic_tokens,
            )
            priority_pool.extend(direct_search)

    for idx, kw in enumerate(keywords):
        if len(priority_pool) + len(extra_pool) >= 20:
            break
        imgs = search_wiki_and_collect(
            WIKI_API, kw, seen_urls,
            max_per_kw=2, topic=topic, topic_tokens=topic_tokens,
        )
        extra_pool.extend(imgs)

    if len(priority_pool) + len(extra_pool) < 5 and keywords:
        extra = search_wiki_and_collect(
            WIKI_API, keywords[0], seen_urls,
            max_per_kw=5, topic=topic, topic_tokens=topic_tokens,
        )
        extra_pool.extend(extra)

    if len(priority_pool) + len(extra_pool) < 3:
        try:
            r = session.get(RU_WIKI_API, params={
                "action": "query", "list": "search", "srsearch": topic,
                "format": "json", "srlimit": 5, "srnamespace": 0,
            }, headers=HEADERS, timeout=8)
            ru_results = r.json().get("query", {}).get("search", [])
            for result in ru_results:
                imgs = get_images_for_article(
                    RU_WIKI_API, result["title"], seen_urls,
                    max_images=2, topic_tokens=topic_tokens,
                )
                priority_pool.extend(imgs)
                if len(priority_pool) >= 5:
                    break
        except Exception:
            pass

    random.shuffle(extra_pool)
    return priority_pool + extra_pool


# ─────────────────────────────────────────────
# Генерация слайдов
# ─────────────────────────────────────────────

FALLBACK_IMAGES = [
    "https://images.unsplash.com/photo-1497633762265-9d179a990aa6?w=1200",
    "https://images.unsplash.com/photo-1503676260728-1c00da094a0b?w=1200",
    "https://images.unsplash.com/photo-1451187580459-43490279c0fa?w=1200",
    "https://images.unsplash.com/photo-1532012197267-da84d127e765?w=1200",
    "https://images.unsplash.com/photo-1456513080510-7bf3a84b82f8?w=1200",
]


def generate_slides_ai(topic, profile, structure):
    final_slides = []
    image_pool = get_smart_image_pool(topic)

    profile_instructions = {
        'dyslexia': (
            "Пиши предельно просто: короткие слова, простые конструкции. "
            "Избегай сложноподчинённых предложений."
        ),
        'adhd': (
            "Пиши тезисно: каждая мысль — отдельное короткое предложение. "
            "Никаких длинных перечислений."
        ),
        'vision': (
            "Пиши чётко, без воды: только суть. "
            "Каждое предложение — законченная мысль."
        ),
        'default': (
            "Пиши грамотно и академично, соблюдая все нормы русского языка. "
            "Предложения — средней длины, без канцеляризмов и воды."
        ),
    }
    instr = profile_instructions.get(profile, profile_instructions['default'])

    sys_prompt = (
        "Ты — опытный педагог и редактор учебных материалов. "
        "Твоя задача — написать содержательный текст для слайда презентации на русском языке. "
        "Требования к тексту:\n"
        "• Ровно 4–5 коротких предложений.\n"
        "• Каждое предложение — не длиннее 15 слов.\n"
        "• Только проверенные факты, точные даты и имена.\n"
        "• Соблюдай все нормы русского языка.\n"
        "• Никакого «воды», повторов, вводных слов и канцелярита.\n"
        f"• Стиль изложения: {instr}\n"
        "Ответ — СТРОГО JSON вида: {\"content\": \"текст слайда\"}. "
        "Никакого другого текста вне JSON."
    )

    for i, item in enumerate(structure):
        title = item.get("title") if isinstance(item, dict) else item.title
        num = i + 1

        user_prompt = (
            f"Тема презентации: «{topic}».\n"
            f"Заголовок слайда: «{title}».\n"
            "Напиши 4–5 коротких предложений по теме этого слайда."
        )

        # 1. Генерируем контент слайда
        raw = generate_text(sys_prompt, user_prompt, max_tokens=350, temp=0.3)
        parsed = clean_json_response(raw)
        content_raw = parsed.get('content', raw) if parsed else raw
        content = smart_truncate(clean_text(content_raw))

        # 2. Выбираем изображение
        if image_pool:
            img_url = image_pool[i % len(image_pool)]
        else:
            img_url = FALLBACK_IMAGES[i % len(FALLBACK_IMAGES)]

        # 3. Генерируем alt-текст с передачей готового контента слайда
        #    Обёртка try/except гарантирует, что сбой alt не уронит весь слайд
        try:
            image_alt = generate_image_alt(
                topic=topic,
                slide_title=title,
                profile=profile,
                slide_content=content,   # ← передаём готовый контент
                image_url=img_url,
            )
        except Exception as e:
            print(f"⚠️ Не удалось сгенерировать alt для слайда {num}: {e}")
            image_alt = f"Иллюстрация к слайду «{title}» по теме «{topic}»."

        final_slides.append({
            "number": num,
            "title": title,
            "content": content,
            "image_url": img_url,
            "image_alt": image_alt,
            "image_prompt": title
        })

    return final_slides


def generate_structure_ai(topic, profile, slides_count: int = 7):
    """
    Генерирует структуру презентации: общий заголовок и список заголовков слайдов.

    Параметры:
        topic:        тема презентации (произвольная строка).
        profile:      профиль адаптации (default / dyslexia / adhd / vision).
                      На формирование структуры влияет только через косвенные
                      правила генерации (стиль заголовков), здесь — никак
                      отдельно не учитывается.
        slides_count: желаемое количество слайдов (1..15). По умолчанию 7 —
                      значение, обратносовместимое со старыми клиентами,
                      которые не передают это поле. Валидация диапазона
                      выполняется на уровне Pydantic-модели StructureRequest
                      (см. models.py, Field(ge=1, le=15)). Здесь — дополнительная
                      защитная клампинг-проверка на случай прямого вызова
                      функции в обход HTTP-слоя (тесты, соседние модули).

    Возвращает:
        dict с ключами "title" (общий заголовок презентации) и "slides"
        (список словарей {"number", "title"} длиной <= slides_count).
    """
    # Защитный клампинг: даже если функция вызвана напрямую (из теста или
    # соседнего модуля) с невалидным значением, приведём к допустимому
    # диапазону, чтобы не уронить генерацию.
    if not isinstance(slides_count, int) or isinstance(slides_count, bool) or slides_count < 1:
        slides_count = 7
    if slides_count > 15:
        slides_count = 15

    sys_p = (
        "Ты — методист, составляющий план учебной презентации. "
        "Требования к заголовкам слайдов:\n"
        "• Каждый заголовок — не более трёх слов.\n"
        "• Пиши заголовки в обычном регистре.\n"
        "• Не используй союз «и» для перечисления.\n"
        "• Заголовки должны быть конкретными, по существу темы.\n"
        f"• Составь РОВНО {slides_count} слайдов — не больше и не меньше.\n"
        "Ответ — СТРОГО JSON вида: {\"title\": \"...\", \"structure\": [\"...\", ...]}. "
        "Никакого другого текста вне JSON."
    )
    user_p = f"Тема: {topic}. Составь план из {slides_count} слайдов."
    # С запасом: 15 заголовков по ~3 слова + JSON-обвязка ≈ 100–150 токенов;
    # 450 — комфортный потолок, чтобы модель не обрезала ответ на середине.
    raw = generate_text(sys_p, user_p, max_tokens=450, temp=0.3)
    data = clean_json_response(raw) or {}
    return {
        "title": clean_text(data.get("title", topic)),
        "slides": [
            {"number": i + 1, "title": t}
            for i, t in enumerate(data.get("structure", [])[:slides_count])
        ]
    }
