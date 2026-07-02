"""
provider.py — Sumber kebenaran "provider LLM aktif" dan daftar model live.

Semua provider dipakai lewat SDK `openai` (endpoint chat-completions yang
kompatibel), jadi pindah provider = ganti (api_key, base_url, model). Qwen
tetap default. Bisa di-toggle saat jalan: ketik nama provider, atau lewat
menu /model (pilih provider lalu pilih model — daftar diambil live dari
endpoint /models provider itu, dengan fallback kurasi bila fetch gagal).

Catatan Claude/Anthropic: integrasi langsung ke Anthropic harus lewat SDK
`anthropic` resmi (bukan shim OpenAI-compatible), jadi belum ada di tabel
ini. Model-model Claude tetap bisa dipakai lewat OpenRouter.

Tiap entri membawa metadata untuk wizard onboarding & menu model:
  env        — nama env var API key (untuk ditulis ke .env)
  model_env  — nama env var model default (untuk persist pilihan /model)
  url        — tempat mendaftar / mengambil key
  prefix     — awalan key untuk validasi ringan ('' = terima apa saja)
  needs_key  — False untuk provider lokal tanpa key (Ollama)
  fallback   — daftar model kurasi bila fetch live gagal
  skip       — potongan nama model yang disaring dari daftar live
               (model non-chat: embedding, audio, dsb.)

Modul ini hanya bergantung pada `config` (hindari impor siklik).
"""

import re

from . import config

_PROVIDERS = {
    "qwen": {
        "name": "Qwen",
        "api_key": config.QWEN_API_KEY,
        "base_url": config.QWEN_BASE_URL,
        "model": config.QWEN_MODEL,
        "headers": {},
        "cmd": {"qwen", "kwen", "kuen", "ke qwen"},
        "env": "DASHSCOPE_API_KEY",
        "model_env": "QWEN_MODEL",
        "url": "https://dashscope.aliyun.com",
        "prefix": "sk-",
        "fallback": ["qwen-plus", "qwen-max", "qwen-turbo", "qwen-flash",
                     "qwen3-coder-plus"],
        "skip": ("embedding", "tts", "asr", "ocr", "rerank", "wan", "realtime",
                 "image", "audio", "video", "livetranslate", "mt-plus", "mt-turbo"),
    },
    "openai": {
        "name": "OpenAI",
        "api_key": config.OPENAI_API_KEY,
        "base_url": config.OPENAI_BASE_URL,
        "model": config.OPENAI_MODEL,
        "headers": {},
        "cmd": {"openai", "open ai", "gpt", "chatgpt", "ke openai"},
        "env": "OPENAI_API_KEY",
        "model_env": "OPENAI_MODEL",
        "url": "https://platform.openai.com/api-keys",
        "prefix": "sk-",
        "fallback": ["gpt-5.1", "gpt-5.1-mini", "gpt-4o", "gpt-4o-mini"],
        # /models OpenAI berisi banyak model non-chat -> saring agresif.
        "skip": ("embedding", "whisper", "tts", "audio", "realtime", "image",
                 "dall-e", "moderation", "transcribe", "davinci", "babbage",
                 "computer-use", "codex"),
    },
    "openrouter": {
        "name": "OpenRouter",
        "api_key": config.OPENROUTER_API_KEY,
        "base_url": config.OPENROUTER_BASE_URL,
        "model": config.OPENROUTER_MODEL,
        # Header opsional OpenRouter (untuk atribusi/ranking; tidak wajib).
        "headers": {
            "HTTP-Referer": "https://github.com/ediiloupatty/voice-coding-assistant",
            "X-OpenRouter-Title": "Voca",
        },
        # Body tambahan: aktifkan reasoning (model berpikir dulu).
        "extra_body": (
            {"reasoning": {"enabled": True}} if config.OPENROUTER_REASONING else {}
        ),
        "cmd": {"openrouter", "open router", "router", "ke openrouter"},
        "env": "OPENROUTER_API_KEY",
        "model_env": "OPENROUTER_MODEL",
        "url": "https://openrouter.ai/keys",
        "prefix": "sk-or-",
        # Satu key OpenRouter = akses Claude, GPT, Gemini, Grok, Llama, dll.
        "fallback": ["anthropic/claude-sonnet-5", "anthropic/claude-opus-4.8",
                     "openai/gpt-5.1", "google/gemini-2.5-pro",
                     "x-ai/grok-4", "meta-llama/llama-3.3-70b-instruct",
                     "openai/gpt-oss-120b:free"],
        "skip": (),
    },
    "deepseek": {
        "name": "DeepSeek",
        "api_key": config.DEEPSEEK_API_KEY,
        "base_url": config.DEEPSEEK_BASE_URL,
        "model": config.DEEPSEEK_MODEL,
        "headers": {},
        # Mode thinking DeepSeek (berpikir dulu, usaha reasoning tinggi).
        "extra_body": (
            {"thinking": {"type": "enabled"}, "reasoning_effort": "high"}
            if config.DEEPSEEK_THINKING else {}
        ),
        "cmd": {"deepseek", "deep seek", "dipsik", "ke deepseek"},
        "env": "DEEPSEEK_API_KEY",
        "model_env": "DEEPSEEK_MODEL",
        "url": "https://platform.deepseek.com/api_keys",
        "prefix": "sk-",
        "fallback": ["deepseek-v4-flash", "deepseek-v4-pro",
                     "deepseek-chat", "deepseek-reasoner"],
        "skip": (),
    },
    "gemini": {
        "name": "Gemini",
        "api_key": config.GEMINI_API_KEY,
        "base_url": config.GEMINI_BASE_URL,
        "model": config.GEMINI_MODEL,
        "headers": {},
        "cmd": {"gemini", "google", "ke gemini"},
        "env": "GEMINI_API_KEY",
        "model_env": "GEMINI_MODEL",
        "url": "https://aistudio.google.com/apikey",
        "prefix": "AIza",
        "fallback": ["gemini-2.5-pro", "gemini-2.5-flash",
                     "gemini-2.5-flash-lite"],
        "skip": ("embedding", "aqa", "imagen", "veo", "tts", "image",
                 "learnlm", "gemma-3n"),
    },
    "xai": {
        "name": "Grok (xAI)",
        "api_key": config.XAI_API_KEY,
        "base_url": config.XAI_BASE_URL,
        "model": config.XAI_MODEL,
        "headers": {},
        "cmd": {"grok", "xai", "x ai", "ke grok"},
        "env": "XAI_API_KEY",
        "model_env": "XAI_MODEL",
        "url": "https://console.x.ai",
        "prefix": "xai-",
        "fallback": ["grok-4", "grok-4-fast", "grok-3-mini"],
        "skip": ("image",),
    },
    "groq": {
        "name": "Groq",
        "api_key": config.GROQ_API_KEY,
        "base_url": config.GROQ_BASE_URL,
        "model": config.GROQ_MODEL,
        "headers": {},
        "cmd": {"groq", "ke groq"},
        "env": "GROQ_API_KEY",
        "model_env": "GROQ_MODEL",
        "url": "https://console.groq.com/keys",
        "prefix": "gsk_",
        "fallback": ["llama-3.3-70b-versatile", "openai/gpt-oss-120b",
                     "qwen/qwen3-32b"],
        "skip": ("whisper", "tts", "guard"),
    },
    "mistral": {
        "name": "Mistral",
        "api_key": config.MISTRAL_API_KEY,
        "base_url": config.MISTRAL_BASE_URL,
        "model": config.MISTRAL_MODEL,
        "headers": {},
        "cmd": {"mistral", "ke mistral"},
        "env": "MISTRAL_API_KEY",
        "model_env": "MISTRAL_MODEL",
        "url": "https://console.mistral.ai/api-keys",
        "prefix": "",          # key Mistral tak punya awalan baku
        "fallback": ["mistral-large-latest", "mistral-medium-latest",
                     "mistral-small-latest", "codestral-latest"],
        "skip": ("embed", "ocr", "moderation", "transcribe", "voxtral"),
    },
    "ollama": {
        "name": "Ollama (lokal)",
        "api_key": config.OLLAMA_API_KEY,
        "base_url": config.OLLAMA_BASE_URL,
        "model": config.OLLAMA_MODEL,
        "headers": {},
        "cmd": {"ollama", "lokal", "local", "ke ollama"},
        "env": "OLLAMA_API_KEY",
        "model_env": "OLLAMA_MODEL",
        "url": "https://ollama.com/download",
        "prefix": "",
        "needs_key": False,    # tanpa key; wizard cukup tes koneksi localhost
        "fallback": [],        # daftar = model yang ter-install di mesin user
        "skip": ("embed",),
    },
}

# Provider aktif (default dari config; jatuh ke 'qwen' kalau tak dikenal).
CURRENT = config.VOCA_PROVIDER if config.VOCA_PROVIDER in _PROVIDERS else "qwen"

# Cache daftar model per provider (per sesi) supaya /model kedua kali instan.
_MODELS_CACHE: dict[str, tuple[list[str], bool]] = {}


def set(prov: str) -> bool:
    """Ganti provider aktif. Return True kalau kode dikenal."""
    global CURRENT
    if prov in _PROVIDERS:
        CURRENT = prov
        return True
    return False


def code() -> str:
    """Kode provider aktif ('qwen' / 'openai' / ...)."""
    return CURRENT


def _cur() -> dict:
    return _PROVIDERS[CURRENT]


def name() -> str:
    """Nama provider aktif."""
    return _cur()["name"]


def name_of(prov: str) -> str:
    """Nama provider tertentu."""
    return _PROVIDERS[prov]["name"]


def api_key() -> str | None:
    return _cur()["api_key"]


def base_url() -> str:
    return _cur()["base_url"]


def model() -> str:
    return _cur()["model"]


def set_model(prov: str, model_id: str) -> None:
    """Ganti model default provider tertentu (untuk sesi berjalan)."""
    _PROVIDERS[prov]["model"] = model_id


def headers() -> dict:
    """Header HTTP tambahan untuk provider aktif (mis. atribusi OpenRouter)."""
    return _cur().get("headers", {})


def extra_body() -> dict:
    """Field body tambahan untuk provider aktif (mis. reasoning OpenRouter)."""
    return _cur().get("extra_body", {})


def has_key(prov: str) -> bool:
    """True kalau provider tertentu sudah punya API key."""
    return bool(_PROVIDERS.get(prov, {}).get("api_key"))


def needs_key(prov: str) -> bool:
    """False untuk provider lokal yang tak butuh key (Ollama)."""
    return _PROVIDERS[prov].get("needs_key", True)


def meta(prov: str) -> dict:
    """Metadata onboarding provider: env, model_env, url, prefix."""
    d = _PROVIDERS[prov]
    return {"env": d["env"], "model_env": d["model_env"],
            "url": d["url"], "prefix": d["prefix"]}


def _saring(prov: str, entries) -> list[str]:
    """Susun daftar model dari respons /models: buang non-chat, urutkan terbaru dulu.

    `entries` = objek dengan .id dan (opsional) .created — dipisah dari fetch
    supaya gampang dites tanpa jaringan.
    """
    skip = _PROVIDERS[prov]["skip"]
    hasil = []
    for m in entries:
        mid = getattr(m, "id", "") or ""
        mid = mid.removeprefix("models/")          # Gemini memakai 'models/...'
        if not mid or any(s in mid.lower() for s in skip):
            continue
        hasil.append((getattr(m, "created", None) or 0, mid))
    hasil.sort(key=lambda t: (-t[0], t[1]))
    # Hilangkan duplikat sambil menjaga urutan. (dict.fromkeys, bukan set() —
    # nama 'set' di modul ini sudah dipakai fungsi ganti-provider.)
    return list(dict.fromkeys(mid for _, mid in hasil))


def list_models(prov: str, timeout: float = 15.0) -> tuple[list[str], bool]:
    """Daftar model provider: (models, live).

    Fetch live dari endpoint /models (OpenAI-compatible, jadi selalu terkini).
    Gagal (offline / endpoint tak mendukung) -> fallback kurasi, live=False.
    Hasil live di-cache per sesi.
    """
    if prov in _MODELS_CACHE:
        return _MODELS_CACHE[prov]
    d = _PROVIDERS[prov]
    try:
        from openai import OpenAI
        client = OpenAI(api_key=d["api_key"] or "-", base_url=d["base_url"],
                        default_headers=d.get("headers") or None, timeout=timeout)
        models = _saring(prov, list(client.models.list()))
        if models:
            _MODELS_CACHE[prov] = (models, True)
            return models, True
    except Exception:
        pass
    # Fallback: daftar kurasi + model aktif saat ini di urutan pertama.
    models = list(d["fallback"])
    if d["model"] not in models:
        models.insert(0, d["model"])
    return models, False


def detect_command(teks: str) -> str | None:
    """Deteksi perintah ganti provider dari ucapan/ketikan pendek.

    Return kode provider kalau teks jelas perintah ganti provider, else None.
    Dibatasi ucapan pendek (<=3 kata) agar tak salah memicu di tengah kalimat.
    """
    bersih = re.sub(r"[^\w\s]", "", teks.lower()).strip()
    if not bersih or len(bersih.split()) > 3:
        return None
    for kode, data in _PROVIDERS.items():
        if bersih in data["cmd"]:
            return kode
    return None
