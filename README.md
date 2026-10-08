# AISector-MoGent

AI Investment Multi-Agent System untuk analisis saham IDX. Backend Python +
Ollama (LLM lokal), data via Sectors Financial API v2. Fitur inti: **Agent
Factory** (membuat agent personalisasi dari agent yang ada tanpa menghapus/
mengubah agent lama) dan **grounding anti-halusinasi** (setiap angka dapat
ditelusuri ke output tool).

Output utama berupa **REST API (FastAPI)** siap integrasi React, plus **CLI**
untuk pengetesan di terminal.

## Prasyarat

- Python 3.11+ (teruji di 3.13)
- Ollama berjalan dengan model `qwen2.5:7b` dan `deepseek-r1:7b`
  ```bash
  ollama serve
  ollama pull qwen2.5:7b
  ollama pull deepseek-r1:7b
  ```
- File `.env` berisi `SECTORS_API_KEY` (sudah disiapkan)

## Instalasi

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Menjalankan CLI (pengetesan terminal)

```bash
python main.py            # mode normal
python main.py --debug    # tampilkan trace orkestrasi lengkap
```

Perintah di dalam REPL:
```
/agents                      daftar agent (base + derived)
/agents show <id>            tampilkan spec agent
/agents lineage <id>         tampilkan asal-usul agent turunan
exit                         keluar
```

Contoh alur demo:
```
User > Saya pensiunan, ingin menjaga kekayaan tapi tetap tumbuh pelan.
       Apakah BBCA cocok? Jelaskan sederhana.
```
→ Orchestrator mendeteksi persona campuran → Agent Factory COMPOSE+MODIFY
`investment_guide` + `wealth_guardian` → agent turunan baru dibuat (base tetap
utuh) → jawaban grounded.

## Menjalankan API (output utama untuk React)

```bash
uvicorn backend.api:app --reload --port 8000
# atau
python -m backend.api
```

Endpoint:

| Method | Path | Fungsi |
|---|---|---|
| GET | `/health` | status layanan, Ollama, API key |
| GET | `/config` | konfigurasi publik (tanpa secret) |
| POST | `/query` | entri utama: `{ "query": "...", "debug": false }` |
| GET | `/agents` | daftar kartu agent (base + derived) |
| GET | `/agents/{id}` | spec lengkap agent |
| GET | `/agents/{id}/lineage` | asal-usul agent turunan |
| GET | `/tools` | manual tool UTCP |

Contoh:
```bash
curl -X POST http://localhost:8000/query \
  -H "Content-Type: application/json" \
  -d '{"query":"Bagaimana fundamental BBCA?"}'
```

## Verifikasi

```bash
python tests_fast.py       # 59 cek deterministik (factory, grounding, API, yfinance)
```

## Arsitektur singkat

```
CLI / API
   │
   ▼
Orchestrator ── Intent/Persona ── Agent Factory (compose/modify/reuse)
   │                                   │ (append-only, base read-only + hash)
   ▼                                   ▼
Agent Runner (spec JSON) ── A2A ── Specialists
   │
   ▼
UTCP Tool Registry → Sectors API   (cache per-request, dedup)
   │
   ▼
Grounding: Evidence Store → Fact Ledger → Number Validator
           Identity Lock · Sanity Check · No-Data Gate
   │
   ▼
Synthesizer (tanpa fakta baru) → Jawaban akhir
```

Prinsip kunci:
- **Fakta dari tool, bahasa dari LLM.** LLM hanya menulis penanda `{{f_xxx}}`;
  Python merender angka. Angka liar ditolak Number Validator.
- **Agent tidak pernah dihapus/ditimpa.** Base agent read-only (hash dikunci),
  agent turunan append-only + lineage + versi.
- **Tidak ada data = tidak ada klaim.** No-Data Gate memblokir LLM bila tak ada
  evidence valid (mis. BI Rate ditolak jujur).

## Struktur

```
main.py                 CLI
backend/api.py          FastAPI (output utama)
backend/orchestrator/   intent, router, synthesizer, orchestrator
backend/agent_factory/  factory, registry, merge_rules, validator, smoke_test, fingerprint, lineage
backend/grounding/      evidence_store, fact_ledger, number_validator, no_data_gate, sanity_checks, identity_lock, glossary
backend/runtime/        agent_runner, facts_extractor
backend/specialists/    invoker
backend/a2a/            protocol, agent_card, agent_registry
backend/utcp/           client, registry, cache, envelope, manual, yf_client (Yahoo Finance)
backend/llm/            ollama, prompts
backend/sector_templates/  bank.json, general.json
data/agents/            base/ (read-only), derived/ (append-only), registry.json
```

## Catatan ketersediaan data (tier API saat ini)

Terverifikasi tersedia di Sectors API: `company/report` (overview, valuation,
financials, dividend, ownership, peers), `corporate-actions`, `news`,
`idx-total`, `foreign-flow`, `companies` (screener), `index-daily`.

Dua endpoint Sectors mengembalikan **HTTP 404** pada tier key saat ini:
`company/quarterly` dan `company/shareholders`. Keduanya **digantikan secara
transparan oleh Yahoo Finance (yfinance)** untuk ticker IDX (suffix `.JK`),
sehingga tool `get_company_quarterly` dan `get_shareholders` tetap `available`
dengan data nyata:

- `get_company_quarterly` → `yfinance.quarterly_income_stmt` +
  `quarterly_balance_sheet` (revenue, laba, net interest income, ekuitas, aset,
  utang kuartalan + ROE kuartalan tahunan sebagai metrik turunan).
- `get_shareholders` → `yfinance.major_holders` + `institutional_holders`
  (kepemilikan insider %, institusi %, jumlah institusi).

Setiap angka dari yfinance tetap melewati grounding: dibawa sebagai fakta
dengan `evidence_id` + sumber "Yahoo Finance", disanity-check, dan dirender via
Number Validator. Analisis bank memakai `financials` (Sectors) untuk data
tahunan dan `get_company_quarterly` (yfinance) untuk kuartal terbaru; LDR & ROE
dihitung sebagai metrik turunan.

## How to run back end
uvicorn backend.api:app --port 8000
