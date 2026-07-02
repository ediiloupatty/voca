"""
onboarding.py — Wizard setup pertama kali (first-run), ala Claude Code CLI.

Installer tidak lagi menanyakan API key. Saat `voca` dijalankan dan belum ada
provider yang punya key, wizard ini muncul di dalam aplikasi:

    sambutan → pilih provider → masukkan API key (tersembunyi)
    → tes koneksi → simpan ke .env → selesai

`setup_provider()` juga dipakai menu /model: memilih provider yang belum
ber-key langsung membuka alur key + tes koneksi yang sama.

Opsi manual tetap ada: isi .env sendiri (salin dari .env.example) atau set
environment variable — kalau key sudah terdeteksi, wizard tidak pernah muncul.
"""

import sys
from getpass import getpass

from openai import OpenAI

from . import config
from . import provider
from . import ui
from .ui import console

ENV_PATH = config.PROJECT_ROOT / ".env"


# ---------------------------------------------------------------------------
# Tulis .env (pertahankan isi lain, ganti/append baris KEY=...)
# ---------------------------------------------------------------------------
def _tulis_env(updates: dict) -> None:
    contoh = config.PROJECT_ROOT / ".env.example"
    if not ENV_PATH.exists() and contoh.exists():
        ENV_PATH.write_text(contoh.read_text(encoding="utf-8"), encoding="utf-8")

    lines = ENV_PATH.read_text(encoding="utf-8").splitlines() if ENV_PATH.exists() else []
    sisa = dict(updates)
    for i, line in enumerate(lines):
        nama = line.split("=", 1)[0].strip().lstrip("#").strip()
        if nama in sisa:
            lines[i] = f"{nama}={sisa.pop(nama)}"
    for nama, nilai in sisa.items():
        lines.append(f"{nama}={nilai}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


# ---------------------------------------------------------------------------
# Langkah-langkah wizard
# ---------------------------------------------------------------------------
def _sambutan() -> bool:
    """Layar sambutan. Return False bila user memilih isi .env manual."""
    W = ui._lebar()
    garis = f"[accent]{ui.RULE * W}[/]"
    logo = "[bold color(51)]V[/] [bold color(81)]O[/] [bold color(141)]C[/] [bold color(201)]A[/]"

    console.print()
    console.print(garis)
    console.print(f" {logo}  [muted]setup pertama kali[/]")
    console.print(garis)
    console.print()
    console.print(" Selamat datang! Voca butuh satu API key untuk 'otak' AI-nya.")
    console.print(" Tiga langkah singkat: [bold]pilih provider → masukkan key → tes koneksi[/].")
    console.print()
    console.print(f" [muted]Mau isi manual? Ketik 'q' — salin .env.example ke .env di[/]")
    console.print(f" [muted]{ENV_PATH}[/]")
    console.print()
    try:
        jawab = console.input(" [accent]ENTER untuk mulai[/] [muted]· q keluar[/] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return jawab != "q"


def _pilih_provider() -> str | None:
    """Langkah 1: menu panah pilih provider. Return kode provider atau None."""
    console.print(f"\n [muted]Langkah 1/3[/] [bold]Pilih provider AI[/]\n")
    opsi = []
    for k, v in provider._PROVIDERS.items():
        opsi.append({
            "code": k,
            "name": v["name"],
            "model": v["model"],
            "configured": provider.has_key(k),
            "is_current": k == provider.code(),
        })
    pilih = ui.pilih_model(opsi, indeks_aktif=0)
    return None if pilih is None else opsi[pilih]["code"]


def _minta_key(kode: str) -> str | None:
    """Langkah 2: input API key tersembunyi + validasi awalan. None bila batal."""
    meta = provider.meta(kode)
    console.print(f"\n [muted]Langkah 2/3[/] [bold]Masukkan API key {provider.name_of(kode)}[/]")
    console.print(f" [muted]Belum punya? Daftar di: {meta['url']}[/]")
    console.print(f" [muted]Key tidak ditampilkan saat diketik · kosongkan untuk batal[/]\n")

    contoh = f"{meta['prefix']}..." if meta["prefix"] else "..."
    while True:
        try:
            key = getpass(f"   API Key ({contoh}): ").strip()
        except (EOFError, KeyboardInterrupt):
            return None
        if not key:
            return None
        if key.startswith(meta["prefix"]):
            return key
        ui.error(f"Key tidak valid — harus diawali '{meta['prefix']}'. Coba lagi.")


def _tes_koneksi(kode: str, key: str) -> bool:
    """Langkah 3: satu panggilan kecil ke provider untuk memastikan key hidup."""
    data = provider._PROVIDERS[kode]
    console.print(f"\n [muted]Langkah 3/3[/] [bold]Tes koneksi[/]")
    try:
        with console.status(f"[muted]menghubungi {data['name']} ({data['model']})…[/]",
                            spinner="dots", spinner_style="accent"):
            client = OpenAI(api_key=key, base_url=data["base_url"],
                            default_headers=data.get("headers") or None, timeout=30)
            client.chat.completions.create(
                model=data["model"],
                messages=[{"role": "user", "content": "ping"}],
                max_tokens=1,
                extra_body=data.get("extra_body") or None,
            )
        console.print(" [success]● Koneksi berhasil — key valid.[/]")
        return True
    except KeyboardInterrupt:
        return False
    except Exception as e:
        ui.error(f"Tes gagal: {e}")
        return False


def _simpan(kode: str, key: str) -> None:
    """Simpan key + provider default ke .env dan terapkan ke sesi berjalan."""
    _tulis_env({provider.meta(kode)["env"]: key, "VOCA_PROVIDER": kode})
    provider._PROVIDERS[kode]["api_key"] = key
    provider.set(kode)


def simpan_model(kode: str, model_id: str) -> None:
    """Persist pilihan model /model ke .env dan terapkan ke sesi berjalan."""
    _tulis_env({provider.meta(kode)["model_env"]: model_id, "VOCA_PROVIDER": kode})
    provider.set_model(kode, model_id)
    provider.set(kode)


def setup_provider(kode: str) -> bool:
    """Alur key untuk SATU provider: minta key → tes → simpan.

    Dipakai wizard first-run maupun menu /model saat provider belum ber-key.
    Provider tanpa key (Ollama) langsung ke tes koneksi. Return True bila
    tersimpan.
    """
    if provider.needs_key(kode):
        key = _minta_key(kode)
        if key is None:
            return False
    else:
        key = "ollama"   # placeholder — SDK openai butuh string non-kosong
        console.print(f"\n [muted]{provider.name_of(kode)} tidak butuh API key — "
                      f"langsung tes koneksi.[/]")

    if _tes_koneksi(kode, key):
        _simpan(kode, key)
        return True

    # Tes gagal: biarkan user memutuskan (ala Claude Code: tak memaksa ulang).
    pilihan = ui.pilih_lanjutan()
    if pilihan == "simpan":
        _simpan(kode, key)
        return True
    if pilihan == "ulang":
        return setup_provider(kode)
    return False


def _jalankan_wizard() -> bool:
    """Seluruh alur wizard first-run. Return True bila setup berhasil."""
    if not _sambutan():
        return False

    while True:
        kode = _pilih_provider()
        if kode is None:
            return False
        if setup_provider(kode):
            break
        # batal di tengah -> balik ke pilihan provider

    console.print()
    console.print(f" [success]✓ Setup selesai.[/] Key tersimpan di [muted]{ENV_PATH}[/]")
    console.print(" [muted]Ganti provider/model kapan saja: ketik /model saat Voca jalan.[/]")
    console.print(" [muted]Key provider lain bisa ditambah manual di .env.[/]\n")
    return True


def _petunjuk_manual() -> None:
    console.print()
    console.print(" Setup dilewati. Isi key manual lalu jalankan lagi:")
    console.print(f"   [bold]1.[/] salin [muted].env.example[/] ke [muted].env[/] di {config.PROJECT_ROOT}")
    console.print("   [bold]2.[/] isi API key provider pilihanmu (mis. DASHSCOPE_API_KEY)")
    console.print()


# ---------------------------------------------------------------------------
# Pintu masuk — dipanggil main() sebelum apa pun
# ---------------------------------------------------------------------------
def pastikan_siap() -> None:
    """Pastikan ada provider dengan API key; jalankan wizard bila belum ada.

    - Provider aktif sudah punya key  → langsung lanjut (jalur manual/.env).
    - Provider lain yang punya key    → otomatis pindah ke situ.
    - Tidak ada key sama sekali       → wizard first-run; batal = keluar rapi.
    """
    if provider.has_key(provider.code()):
        return

    terisi = [k for k in provider._PROVIDERS if provider.has_key(k)]
    if terisi:
        provider.set(terisi[0])
        ui.info(f"Provider default belum ber-key; pakai {provider.name()} dari .env.")
        return

    if not _jalankan_wizard():
        _petunjuk_manual()
        sys.exit(1)
