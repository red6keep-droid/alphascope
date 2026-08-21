"""커버 이미지 생성 (Pollinations.ai 1차 → Hugging Face Inference API 2차)

Gemini가 생성한 image_prompt(영문 1문장)에 고정 스타일 접미사를 붙여
이미지를 생성한 뒤 Pillow로 WebP(quality=80)로 압축 저장한다.

우선순위:
1. Pollinations.ai — API 키 불필요, flux → turbo 모델 순서 재시도
2. Hugging Face Inference API — HF_TOKEN 필요, FLUX.1-schnell

환경 변수:
    HF_TOKEN   Hugging Face Access Token (fallback 시에만 필요)
    BLOG_URL   Pollinations referrer 파라미터용 (선택)
"""

import io
import os
import time
import urllib.parse

import requests

try:
    from PIL import Image
except ImportError:
    Image = None

POLLINATIONS_URL = "https://image.pollinations.ai/prompt/{prompt}"
POLLINATIONS_MODELS = ["flux", "turbo"]
POLLINATIONS_TIMEOUT = 90
ATTEMPTS_PER_MODEL = 2
RETRY_SLEEP_SECONDS = 3

HF_MODEL = "black-forest-labs/FLUX.1-schnell"

STYLE_SUFFIX = (
    ", clean minimalist 3D corporate illustration, deep blue and navy palette, "
    "professional financial infographic style, no text, no numbers, no letters"
)

WIDTH = 1024
HEIGHT = 576
WEBP_QUALITY = 80
MIN_IMAGE_BYTES = 10 * 1024


def _full_prompt(image_prompt):
    return str(image_prompt).strip() + STYLE_SUFFIX


def _referrer():
    return os.environ.get("BLOG_URL", "https://alpha-scope.blogspot.com/").strip()


def _pollinations_url(prompt, model):
    encoded = urllib.parse.quote(prompt)
    referrer = urllib.parse.quote(_referrer())
    return (
        f"https://image.pollinations.ai/prompt/{encoded}"
        f"?model={model}&nologo=true&referrer={referrer}"
        f"&format=jpeg&width={WIDTH}&height={HEIGHT}"
    )


def _looks_like_image(data):
    if len(data) < MIN_IMAGE_BYTES:
        return False
    if data[:3] == b"\xff\xd8\xff":        # JPEG
        return True
    if data[:8] == b"\x89PNG\r\n\x1a\n":   # PNG
        return True
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":  # WebP
        return True
    return False


def _fetch(url):
    resp = requests.get(
        url,
        timeout=POLLINATIONS_TIMEOUT,
        headers={"User-Agent": "alpha-scope-daily-report/1.0"},
    )
    if resp.status_code != 200:
        raise RuntimeError(f"HTTP {resp.status_code}")
    if not _looks_like_image(resp.content):
        raise RuntimeError(f"응답이 유효한 이미지가 아님 ({len(resp.content)} bytes)")
    return resp.content


def _try_pollinations(prompt):
    errors = []
    for model in POLLINATIONS_MODELS:
        url = _pollinations_url(prompt, model)
        for attempt in range(1, ATTEMPTS_PER_MODEL + 1):
            try:
                print(f"[Pollinations] model={model} 시도 {attempt}/{ATTEMPTS_PER_MODEL}")
                return _fetch(url), f"pollinations:{model}"
            except Exception as e:
                print(f"[Pollinations] 실패({attempt}/{ATTEMPTS_PER_MODEL}): {e}")
                errors.append(f"{model}: {e}")
                if attempt < ATTEMPTS_PER_MODEL:
                    time.sleep(RETRY_SLEEP_SECONDS)
    raise RuntimeError(" / ".join(errors))


def _try_huggingface(prompt):
    token = os.environ.get("HF_TOKEN", "").strip()
    if not token:
        raise RuntimeError("HF_TOKEN 미설정 - Hugging Face fallback 사용 불가")
    from huggingface_hub import InferenceClient

    print(f"[HuggingFace] model={HF_MODEL} 시도")
    client = InferenceClient(HF_MODEL, token=token)
    image = client.text_to_image(prompt, width=WIDTH, height=HEIGHT)
    buf = io.BytesIO()
    image.save(buf, format="JPEG", quality=92)
    data = buf.getvalue()
    if not _looks_like_image(data):
        raise RuntimeError("Hugging Face 응답이 유효한 이미지가 아님")
    return data, f"huggingface:{HF_MODEL}"


def _save_webp(data, out_path):
    if Image is None:
        raise RuntimeError("pillow 미설치 - WebP 변환 불가 (pip install pillow)")
    img = Image.open(io.BytesIO(data)).convert("RGB")
    img.save(out_path, "WEBP", quality=WEBP_QUALITY)


PROVIDERS = [
    ("Pollinations.ai", _try_pollinations),
    ("Hugging Face", _try_huggingface),
]


def generate_image(image_prompt, out_path):
    """이미지를 생성해 out_path(WebP)로 저장한다. 성공 시 True, 전부 실패 시 False."""
    prompt = _full_prompt(image_prompt)
    last_error = None
    for name, provider in PROVIDERS:
        try:
            data, source = provider(prompt)
            _save_webp(data, out_path)
            size_kb = os.path.getsize(out_path) // 1024
            print(f"[이미지] 생성 완료 ({source}) -> {out_path} ({size_kb}KB)")
            return True
        except Exception as e:
            last_error = e
            print(f"[이미지] {name} 실패: {e}")
    print(f"[이미지] 모든 공급자 실패: {last_error}")
    return False


if __name__ == "__main__":
    import sys

    from dotenv import load_dotenv

    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    load_dotenv()
    ok = generate_image(
        "US stock market daily briefing concept",
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "output", "test_cover.webp"),
    )
    sys.exit(0 if ok else 1)
