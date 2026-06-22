import os, requests, uuid, time
from PIL import Image
from io import BytesIO

def download_and_save_image(url, query, base_dir=None):
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
    try:
        # Ставим очень короткий таймаут. Не скачалось за 3 сек — ну и ладно.
        response = requests.get(url, timeout=3, headers=headers, stream=True)
        if response.status_code != 200: return None

        if base_dir:
            save_dir = os.path.join(base_dir, "slides")
        else:
            current_dir = os.path.dirname(os.path.abspath(__file__))
            save_dir = os.path.join(os.path.dirname(current_dir), "media", "slides")

        os.makedirs(save_dir, exist_ok=True)
        filename = f"{uuid.uuid4().hex[:12]}.jpg"
        filepath = os.path.join(save_dir, filename)

        img = Image.open(BytesIO(response.content))
        if img.mode in ("RGBA", "P"): img = img.convert("RGB")
        img.save(filepath, "JPEG", quality=75)
        return f"slides/{filename}"
    except:
        return None
