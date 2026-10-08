"""Prompt builders (PRD 10.4, 10.10, 10.11).

All prompts enforce the grounding contract in text, but the real guarantee
comes from Python validators. Prompts here are deliberately strict about the
"numbers only as {{f_xxx}} markers" rule.
"""
from __future__ import annotations

import json

from backend.grounding import glossary

GROUNDING_RULES = (
    "ATURAN GROUNDING (WAJIB):\n"
    "1. Anda DILARANG menulis angka apa pun secara langsung.\n"
    "2. Setiap angka harus berupa penanda fakta persis seperti {{f_001}}.\n"
    "3. Hanya gunakan penanda fakta yang disediakan. Jangan mengarang fakta/angka.\n"
    "4. Jangan menyebut sektor atau jenis usaha yang bertentangan dengan identitas perusahaan.\n"
    "5. Jika suatu data tidak tersedia, katakan dengan jujur 'data tidak tersedia', jangan menebak.\n"
    "6. Jangan memberi perintah beli/jual. Ini alat edukasi, bukan nasihat investasi.\n"
)


def agent_system_prompt(spec: dict) -> str:
    role = spec.get("role", "Analis saham")
    style = spec.get("reasoning_style", "ringkas dan hati-hati")
    lang_level = (spec.get("output_format") or {}).get("language_level", "standard")
    level_hint = {
        "simple": "Gunakan bahasa yang sangat sederhana untuk pemula; jelaskan istilah.",
        "standard": "Gunakan bahasa Indonesia profesional yang jelas.",
        "expert": "Gunakan bahasa teknis yang padat.",
    }.get(lang_level, "Gunakan bahasa Indonesia yang jelas.")
    return (
        f"Anda adalah {role}.\n"
        f"Gaya penalaran: {style}.\n"
        f"{level_hint}\n\n"
        f"{GROUNDING_RULES}\n"
        f"{glossary.prompt_block()}\n"
    )


def agent_user_prompt(spec: dict, identity_block: str, facts: list[dict],
                      sections: list[str], user_query: str, template_note: str = "",
                      time_context: str = "") -> str:
    facts_json = json.dumps(facts, ensure_ascii=False, indent=1)
    sec = ", ".join(sections)
    tctx = f"KONTEKS WAKTU SAAT INI: {time_context}\n\n" if time_context else ""
    return (
        f"PERTANYAAN PENGGUNA:\n{user_query}\n\n"
        f"{tctx}"
        f"IDENTITAS PERUSAHAAN (ground truth, jangan dibantah):\n{identity_block}\n\n"
        f"{template_note}\n"
        f"FAKTA TERSEDIA (pakai penanda fact_id untuk setiap angka):\n{facts_json}\n\n"
        f"Tulis analisis dengan bagian berikut: {sec}.\n"
        "CARA BERPIKIR (WAJIB):\n"
        "- TAMPILKAN SEMUA DATA yang tersedia kepada pengguna dengan penanda {{f_xxx}}.\n"
        "- Lakukan analisis dari fakta yang TERSEDIA; jangan berhenti karena ada data "
        "yang tidak lengkap. Kerjakan dengan data yang ada dan sebut kekurangannya di 'keterbatasan'.\n"
        "- Setiap angka HARUS ditampilkan kepada pengguna (bukan disembunyikan). Gunakan penanda.\n"
        "- Jangan membahas struktur data internal (duplikat, as_of, fact_id); fokus pada makna bisnis.\n"
        "- Setiap bagian harus berisi analisis nyata dengan data, bukan sekadar narasi tanpa angka.\n"
        "- Selesaikan sampai ada kesimpulan; jangan berhenti di tengah.\n"
        "- Pengguna perlu MELIHAT DATA agar bisa memverifikasi kesimpulan Anda.\n"
        f"Ingat: angka hanya sebagai penanda {{{{f_xxx}}}}. "
        f"Akhiri dengan bagian 'keterbatasan' yang jujur.\n"
    )


def intent_persona_prompt(user_query: str) -> str:
    return (
        "Anda adalah pendeteksi intent dan persona untuk sistem analisis saham IDX.\n"
        "Deteksi HANYA dari ucapan pengguna. Jangan menebak usia/kesehatan/keuangan.\n\n"
        "Kembalikan JSON dengan kunci:\n"
        '  "ticker": simbol saham jika disebut (mis. "BBCA") atau null,\n'
        '  "intent": salah satu ["price","single_metric","fundamental","macro","multi_analysis","education","general_education","out_of_scope"],\n'
        '           ("general_education" = pertanyaan konsep/definisi umum TANPA kode saham, mis. "apa itu EPS"),\n'
        '           ("multi_analysis" = analisis menyeluruh fundamental+makro+katalis untuk satu saham),\n'
        '  "personas": subset dari ["complete_beginner","fundamental_investor","macro_strategist","wealth_preservation","senior_investor"],\n'
        '  "capabilities": subset dari ["investment_education","fundamental_analysis","valuation_analysis","risk_analysis","dividend_analysis","macro_analysis","news_sentiment","catalyst_analysis"],\n'
        '  "modifiers": subset dari ["simple_language","sector_bank","downside_focus"],\n'
        '  "needs_macro_numbers": true/false (true jika minta angka BI Rate/inflasi/kurs)\n\n'
        f"UCAPAN PENGGUNA:\n{user_query}\n\n"
        "Jawab HANYA dengan JSON."
    )


def synthesizer_prompt(user_query: str, agent_blocks: list[dict], facts: list[dict],
                       contradictions: list[str], time_context: str = "") -> str:
    blocks = json.dumps(agent_blocks, ensure_ascii=False, indent=1)
    contra = (", ".join(contradictions) if contradictions
              else "tidak ada kontradiksi terdeteksi")
    tctx = f"KONTEKS WAKTU SAAT INI: {time_context}\n\n" if time_context else ""
    return (
        "Anda adalah Synthesizer. Tugas Anda MENYUSUN SATU ANALISIS yang runtut, "
        "berbasis data, dan bermanfaat untuk pengguna — berdasarkan narasi para agent di bawah.\n"
        f"{GROUNDING_RULES}\n"
        f"{tctx}"
        f"PERTANYAAN PENGGUNA:\n{user_query}\n\n"
        f"NARASI AGENT (sudah tervalidasi, pakai apa adanya sebagai bahan analisis):\n{blocks}\n\n"
        "ATURAN SYNTHESIZER (WAJIB):\n"
        "1. Tulis ANALISIS SUBSTANTIF yang MENAMPILKAN DATA kepada pengguna.\n"
        "2. WAJIB tampilkan angka dari narasi agent (salin penanda yang ada; jangan mengarang baru).\n"
        "3. DILARANG membahas 'data duplikat', 'as_of kosong', 'fact_id', atau struktur data.\n"
        "4. Gabungkan temuan fundamental, makro, berita, dan risiko menjadi kesimpulan yang menyatu.\n"
        "5. Setiap bagian HARUS memiliki data angka jika tersedia di narasi agent.\n"
        "6. Jangan menambah angka/entitas/klaim BARU. Hanya angka yang sudah ada di narasi agent.\n"
        f"7. Kontradiksi: {contra}. Bila ada, sebut singkat di Keterbatasan; jangan dirata-rata.\n"
        "8. Jangan berhenti di tengah; selesaikan analisis sampai ada kesimpulan.\n"
        "9. Pengguna perlu melihat DATA untuk memahami dan memverifikasi kesimpulan.\n\n"
        "Struktur jawaban WAJIB:\n"
        "## Ringkasan\n"
        "## Data Fundamental\n"
        "## Konteks Makro & Katalis\n"
        "## Penilaian Risiko\n"
        "## Kesimpulan\n"
        "## Keterbatasan\n\n"
        "Gunakan Bahasa Indonesia yang jelas. Tampilkan angka dari narasi agent di setiap bagian yang relevan."
    )


def general_education_prompt(user_query: str) -> str:
    """Concept/definition questions with no ticker (PRD 10.12, 12.2).

    Answered as a labeled conceptual explanation. No live data, no specific
    company figures. The number validator still runs on the output.
    """
    return (
        "Anda adalah pemandu investasi untuk pemula. Jawab pertanyaan edukasi "
        "umum berikut dengan Bahasa Indonesia yang sederhana dan jelas.\n\n"
        f"{GROUNDING_RULES}\n"
        "KHUSUS PERTANYAAN UMUM:\n"
        "- Ini penjelasan KONSEPTUAL, bukan data terkini perusahaan tertentu.\n"
        "- Jangan menyebut angka spesifik perusahaan (harga, PER, dsb) karena "
        "tidak ada data tool yang diambil.\n"
        "- Boleh memberi contoh rumus/konsep umum tanpa mengarang nilai nyata.\n"
        "- Jika relevan, akhiri dengan ajakan menyebut kode saham IDX bila "
        "pengguna ingin melihat angka nyata.\n\n"
        f"{glossary.prompt_block()}\n\n"
        f"PERTANYAAN:\n{user_query}\n\n"
        "Jawab langsung, ringkas, dan edukatif."
    )
