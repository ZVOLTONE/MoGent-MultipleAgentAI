# Documentation — AISector-MoGent

Dokumentasi progres pengembangan AI Investment Multi-Agent System.
Versi implementasi: MVP 1.1 (mengikuti `PRD_AISector-MoGent_v1.1.md`) +
Web Card Interface (mengikuti `PRD_AISector-MoGent_Web-Cards_v1.0.md`).
Tanggal: 2026-10-04 (inti) · 2026-10-07 (yfinance + Web Cards).

---

## 1. Ringkasan

Sistem AI multi-agent untuk analisis saham IDX dibangun penuh dari nol.
Backend Python + Ollama (LLM lokal) + Sectors Financial API v2. Interface:
**CLI** (pengetesan terminal), **FastAPI** (API utama), dan **Web React**
(deck kartu analisis).

Tiga fitur inti sudah berfungsi dan terverifikasi:

1. **Agent Factory** — membuat agent personalisasi (compose/modify/reuse) dari
   agent yang ada, tanpa menghapus/mengubah agent lama.
2. **Grounding anti-halusinasi** — setiap angka pada jawaban dapat ditelusuri
   ke `evidence_id` dari output tool.
3. **Web Card Interface + Presentation Composer** — output analisis disajikan
   sebagai deck kartu geser di website React; satu base agent khusus menyusun
   kartu dari fakta tervalidasi tanpa menganalisis ulang (lihat bagian 17).

Status terakhir: **backend `tests_fast.py` 70/70 lulus**, **frontend
`npm run build` sukses**, 9 base agent (termasuk `presentation_composer`),
`/query` + `/cards` terverifikasi live.

---

## 2. Lingkungan yang Terverifikasi

| Komponen | Status |
|---|---|
| Python | 3.13.7 |
| Ollama | berjalan di `http://localhost:11434` |
| Model `qwen2.5:7b` | tersedia → Orchestrator, Synthesizer, Agent runtime |
| Model `deepseek-r1:7b` | tersedia → Specialist (`<think>` dibuang) |
| Sectors API key | valid (dari `.env`, tidak pernah di-hardcode) |
| Virtualenv | `.venv/` dengan fastapi, uvicorn, requests, python-dotenv, pydantic |

Konfigurasi `.env` pengguna memakai `MODEL_NAME`/`MODEL_NAME_2`; `config.py`
dibuat mendukung nama tersebut sekaligus nama PRD (`ORCHESTRATOR_MODEL`, dst).

---

## 3. Verifikasi API Sectors (dilakukan sebelum coding)

Sebelum menulis UTCP, respons API nyata diperiksa agar field-mapping benar
(mencegah bug UAT "PER bernilai miliaran").

**Tersedia (HTTP 200) pada tier key ini:**

- `company/report` section: `overview`, `valuation`, `financials`, `dividend`
  - `overview.sector="Financials"`, `overview.sub_sector="Banks"`, `market_cap`, `last_close_price`
  - `valuation.historical_valuation[]` (per tahun: `pe`, `pb`, `ps`), `forward_pe`, `intrinsic_value`
  - `financials.historical_financials[]` (field bank: `gross_loan`, `total_deposit`, `net_interest_income`, `total_equity`, `earnings`)
  - `dividend.historical_dividends{year}` (`total_yield`, `total_dividend`)
- `company/corporate-actions/{symbol}`, `news/`, `idx-total/`, `foreign-flow/{symbol}`,
  `companies/` (screener), `index-daily/{index}` (kode indeks **lowercase**, mis. `idx30`)

**Tidak tersedia (HTTP 404) pada tier ini:**

- `company/quarterly`, `company/quarterly-dates`, `company/shareholders`

Konsekuensi desain: tool-tool ini tetap didaftarkan dengan flag `available:false`
agar **No-Data Gate** dapat mendemonstrasikan penolakan jujur. Analisis bank
memakai `financials` section; **LDR** dan **ROE** dihitung sebagai metrik turunan.

- Ticker palsu `ZZZZ` → HTTP 404 `{"error":"Given stock symbol does not exist."}`.
- Header auth: raw key pada `Authorization` (tanpa `Bearer`).

---

## 4. Arsitektur yang Diimplementasikan

```
Web React (frontend/) ──POST /cards──┐
CLI (main.py) / API (backend/api.py)  │
        │                             │
        ▼                             │
   Orchestrator ── Intent/Persona Detection
        │          Capability Matching + Routing (4 jalur)
        │          └─ Agent Factory (compose / modify / reuse)
        ▼
   Agent Runner (menjalankan spec JSON) ── A2A ── Specialists
        │
        ▼
   UTCP Tool Registry → Sectors API / yfinance / scraper   (cache per-request + dedup)
        │
        ▼
   Grounding:
     Evidence Store → Fact Ledger → Number Validator
     Identity Lock · Sanity Check · No-Data Gate · Glossary
        │
        ▼
   Synthesizer (tanpa fakta baru, deteksi kontradiksi)
        │
        ▼
   Jawaban akhir (grounded) ── facts + evidence ──▶ Presentation Composer
                                                     (card_builder, deterministik)
                                                           │
                                                           ▼
                                                     Deck kartu (React)
```

---

## 5. Rincian Modul (per layer)

### 5.1 Konfigurasi & fondasi
- `config.py` — loader env, path proyek, masking API key, `as_public_dict()`
  (aman diekspos, tanpa secret), `ensure_dirs()`.
- `requirements.txt`, `.gitignore` (mengecualikan `.env`, derived, conversations).

### 5.2 UTCP (`backend/utcp/`)
- `envelope.py` — `ToolResponse` dengan `result_status` ∈ `{ok, empty, error,
  invalid_schema}`, `status_glyph()` (✓/✗ + alasan), `payload_sha256`.
- `cache.py` — `RequestCache` dedup per-request berdasarkan `(tool, args)`.
  Mengatasi temuan UAT "17 tool call ganda" (T21).
- `client.py` — `SectorsClient`: timeout 30s, retry backoff untuk 429/5xx, **tanpa**
  retry untuk 400/404, deteksi payload kosong, key hanya dari `config`.
- `registry.py` — `ToolRegistry` 11 tool MVP, normalisasi simbol, indeks lowercase,
  flag `available` untuk tool 404.
- `manual.json` — manual tool untuk discovery (gaya A2A/MCP).

### 5.3 Grounding (`backend/grounding/`)
- `evidence_store.py` — `EvidenceStore` per request, `EvidenceRecord` (`ev_XXXX`),
  `has_ok()`, `ok_ids()`.
- `fact_ledger.py` — `FactLedger` (`f_XXX`), `render_markers()` mengganti
  `{{f_xxx}}` dengan nilai terformat (rupiah/triliun/x/%), `facts_for_prompt()`.
- `identity_lock.py` — ground truth sektor dari `overview`; deteksi kontradiksi
  (mis. "pertanian/sawit" pada emiten Financials); `is_bank()`, `template()`.
- `sanity_checks.py` — rentang wajar metrik; menandai anomali (mis. PER miliaran).
- `no_data_gate.py` — memblokir LLM bila tidak ada evidence `ok`.
- `number_validator.py` — `validate()` menolak angka finansial liar; `_is_financial_figure`
  menolak desimal/pemisah ribuan/`%`/`x`/≥3 digit, mengizinkan integer kecil (prosa);
  `correction_instruction` (regen maks 2); `deterministic_template` (fallback tabel).
- `glossary.json` + `glossary.py` — istilah baku ID; daftar istilah terlarang.

### 5.4 LLM (`backend/llm/`)
- `ollama.py` — `OllamaClient.generate/generate_json`, `strip_think()` membuang
  `<think>…</think>`, mode JSON, temperature rendah.
- `prompts.py` — `GROUNDING_RULES`, prompt agent/intent/synthesizer.

### 5.5 Agent Factory (`backend/agent_factory/`)
- `registry.py` — `AgentRegistry`: muat base (read-only) + derived (append-only),
  `verify_integrity()` membandingkan sha256 base dengan `registry.json`
  (`IntegrityError` bila diubah), `register_derived()` menolak overwrite, **tanpa delete**.
- `fingerprint.py` — hash (persona, capability, modifier) ternormalisasi untuk REUSE.
- `merge_rules.py` — `compose()` (union + induk dominan), `apply_overrides()`
  (field MODIFY yang diizinkan vs terlarang), level bahasa paling sederhana menang.
- `validator.py` — tolak: skema invalid, tool di luar whitelist induk,
  `locked_constraints` berkurang, parents > 3, kedalaman lineage > 3.
- `smoke_test.py` — dry-run tanpa data harus `no_data` (bukan karangan).
- `lineage.py` — bangun & render blok lineage.
- `factory.py` — `AgentFactory`: scoring, `decide()` (use_existing/reuse/compose/
  modify/fallback), `create()` (merge → validate → smoke → register append-only).

### 5.6 Runtime (`backend/runtime/`)
- `facts_extractor.py` — map payload nyata ke fakta + sanity + metrik turunan
  bank (LDR, ROE).
- `agent_runner.py` — pipeline per agent: tools → evidence → facts → identity lock
  → no-data gate → LLM (marker-only) → number/identity/glossary validator (regen) →
  fallback deterministik → render marker → output contract (PRD 16).

### 5.7 A2A (`backend/a2a/`)
- `protocol.py` — `A2AMessage`/`A2AResponse`, `A2ABus` (batas kedalaman, dedup task
  identik, `debug_dump()`).
- `agent_card.py`, `agent_registry.py` — kartu & discovery agent.

### 5.8 Specialists (`backend/specialists/`)
- `invoker.py` — menjalankan specialist (spec JSON) via agent_runner lewat A2A;
  hasil merujuk `fact_ids`.

### 5.9 Orchestrator (`backend/orchestrator/`)
- `intent_detector.py` — deteksi intent/persona/capability/modifier (LLM + heuristik).
- `agent_router.py` — pemetaan intent ke 4 jalur.
- `synthesizer.py` — gabung hasil, deteksi kontradiksi sektor, pindahkan `no_data`
  ke keterbatasan, validasi keluaran (fallback gabung narasi), tanpa fakta baru.
- `orchestrator.py` — pipeline utama + **ticker existence gate** (404 → tolak) +
  macro refusal + output contract + `_trace` untuk debug.
- `memory.json` — routing/composition rules, threshold.

### 5.10 Interface
- `main.py` — CLI: banner, `/agents`, `/agents show|lineage <id>`, `--debug`.
- `backend/api.py` — FastAPI: `/health`, `/config`, `/query`, `/cards` (baru),
  `/agents`, `/agents/{id}`, `/agents/{id}/lineage`, `/tools`; CORS aktif untuk React.
- `backend/presentation/` — Presentation Composer: `card_builder.py`,
  `explain.py`, `profiles.py`, `routes.py` (lihat bagian 17).
- `frontend/` — Web React (Vite + TS + Tailwind 4): deck kartu analisis
  (lihat bagian 17.6).

### 5.11 Data
- `data/agents/base/` — 9 base agent (4 persona + 4 specialist +
  `presentation_composer`), immutable.
- `data/agents/derived/` — append-only (profil kartu turunan dibuat di sini
  bila persona terdeteksi).
- `data/agents/registry.json` — indeks + checksum base (termasuk
  `presentation_composer`).
- `backend/sector_templates/` — `bank.json`, `general.json`.

---

## 6. Progres per Fase (PRD section 22)

| Fase | Isi | Status |
|---|---|---|
| 0 | UTCP + Evidence Store + envelope + cache | ✅ selesai & diuji vs API nyata |
| 1 | Ollama → agent dari spec → Fact Ledger → Number Validator | ✅ selesai |
| 2 | Identity Lock + template sektor (bank/general) | ✅ selesai |
| 3 | Multi-agent + A2A + No-Data Gate + Synthesizer + kontradiksi | ✅ selesai |
| 4 | Agent Factory: compose/modify/reuse + registry + hash + lineage | ✅ selesai |
| 5 | Robustness: timeout/retry/fallback/tool failure/ticker 404 | ✅ selesai |

Catatan: sumber data makro (BI Rate/inflasi/kurs) tetap mode market-proxy sesuai
PRD 12.2 — pertanyaan angka makro ditolak jujur.

---

## 7. Hasil Verifikasi

### 7.1 Suite deterministik — `python tests_fast.py` → **26/26 lulus**

Mencakup: T10 (8 base immutable), T12 (tolak tool luar whitelist), T13 (tolak
hapus `locked_constraints`), T15 (hash integrity), T16 (smoke test `no_data`),
T17 (identity BBCA=bank + deteksi "pertanian/sawit"), T19 (ticker `ZZZZ` → 404),
T21 (dedup cache per-request), T22 (number validator menolak `15.3`/`6100`/
`12.806.979.354`/`5%`/`22x`; mengizinkan marker + prosa), sanity anomali PER
miliaran, serta factory compose+modify → reuse dengan base tetap 8.

### 7.2 End-to-end (LLM nyata)

- **Case B (demo utama)**: "Saya pensiunan… bahasa sederhana" → Agent Factory
  **COMPOSE+MODIFY** `wealth_guardian + investment_guide` → `derived_senior_wealth_beginner`,
  5 validasi lulus, `language_level=simple`, base agent tidak berubah, jawaban
  grounded (BBCA = bank).
- **T17** "Analisis fundamental BBCA": sektor bank, **0** kebocoran istilah
  terlarang, **18 fakta semua ber-`evidence_id`** (nol angka tanpa sumber),
  tanpa tool call ganda.
- **T18** "Berapa BI Rate hari ini?": penolakan jujur, tanpa angka.
- **T1** "Berapa harga BBCA?": jalur simple `get_daily_price`.

### 7.3 API (uji live)

`/health` ok (Ollama reachable, key present), `/agents` 8 base, `/tools` 11 tool,
`POST /query` menjalankan factory (`compose_modify`, `base_agents_unchanged=true`),
`/agents/{id}/lineage` menampilkan induk + operasi + alasan.

### 7.4 Keamanan & kualitas kode

- `py_compile` seluruh modul: OK.
- Tidak ada API key hardcoded (hanya `.env`).
- State demo pristine: 8 base, 0 derived, `registry.json` fresh.

---

## 8. Cara Menjalankan

```bash
# setup
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt

# CLI
python main.py            # normal
python main.py --debug    # trace orkestrasi lengkap

# API (output utama untuk React)
uvicorn backend.api:app --reload --port 8000

# verifikasi
python tests_fast.py
```

---

## 9. Pemetaan Temuan UAT → Perbaikan (ringkas)

| Temuan UAT | Perbaikan di implementasi | Bukti |
|---|---|---|
| BBCA disebut "pertanian" | Identity Lock + template bank | T17 lulus (0 kebocoran) |
| PER 12.806.979.354 | Sanity check + field-mapping dari respons nyata | PER = 12.81x; T22 |
| Dividen "belum ada" dari data kosong | Kosong ≠ negatif → `no_data` | No-Data Gate |
| BI Rate/inflasi tanpa tool | No-Data Gate + penolakan jujur | T18 lulus |
| 17 tool call ganda | Cache per-request + dedup | T21 lulus |
| ✓ walau data invalid | ✓ hanya saat `result_status==ok` | glyph UTCP |
| Agent dihapus/ditimpa | Base read-only + hash; derived append-only | T10/T12/T13/T15 |

---

## 10. Keputusan Teknis Penting

1. **Agent = spec JSON** dijalankan satu `agent_runner`. Agent Factory membuat
   agent baru tanpa menulis kode Python baru (sesuai PRD section 21).
2. **Fakta dari tool, bahasa dari LLM.** LLM hanya menulis penanda `{{f_xxx}}`;
   Python merender angka. Number Validator menolak angka liar; fallback tabel
   deterministik bila model membandel.
3. **Ticker existence gate** ditambahkan: probe `overview` sekali (ter-cache),
   404 → tolak sebelum analisis — menutup kebocoran di mana `screen_companies`
   (abai simbol) bisa meloloskan analisis emiten tak-ada.
4. **Tool tak tersedia tetap terdaftar** (`available:false`) agar No-Data Gate
   dapat didemonstrasikan sebagai perilaku jujur, bukan kegagalan senyap.
5. **Number validator di-tune**: hanya memblokir pola angka finansial nyata,
   mengizinkan enumerasi/tahun pada prosa — mengurangi fallback palsu tanpa
   melemahkan proteksi anti-halusinasi.

---

## 11. Keterbatasan Diketahui & Langkah Berikutnya

- Endpoint `quarterly`/`shareholders`/`quarterly-dates` 404 pada tier key saat
  ini → ditangani sebagai `no_data`. Jika tier ditingkatkan, cukup set
  `available:true` di `TOOL_SPECS` tanpa perubahan arsitektur.
- Sumber data makro (BI Rate/inflasi/kurs) belum ditetapkan → mode market-proxy.
- Kualitas model 7B bervariasi; grounding Python menjamin jawaban tetap aman
  walau model keliru (fallback deterministik aktif).
- Langkah React: kontrak JSON `/query` sudah sesuai PRD section 16, CORS aktif.
  Tinggal membangun UI yang mengonsumsi `agent_factory`, `tool_calls`,
  `limitations`, `contradictions`, dan `_trace` (saat `debug:true`).

---

## 12. Revisi Pasca-Uji (2026-10-04, sesi lanjutan)

Dua masalah ditemukan saat uji pengguna dan telah diperbaiki:

### 12.1 Pertanyaan edukasi umum tak terjawab
Sebelumnya "apa itu EPS" dibalas "Mohon sebutkan kode saham" karena orchestrator
selalu menuntut ticker.

**Perbaikan:**
- Intent baru `general_education` untuk pertanyaan konsep/definisi tanpa ticker
  (dipicu kata "apa itu", "jelaskan", "pengertian", "apa bedanya", dll).
- `Orchestrator._run_general_education()` menjawab langsung lewat LLM dengan
  `general_education_prompt` (penjelasan konseptual berlabel, tanpa data terkini).
  Keluaran tetap melewati Number Validator; tidak ada panggilan tool/API.
- Hasil: "apa itu EPS" → jawaban edukatif, **0 tool call**, tanpa ticker.

### 12.2 Cek ticker boros token/kredit API
Sebelumnya keberadaan ticker diperiksa dengan probe `get_company_report`
(memakai kredit API), dan singkatan seperti "EPS"/"ROE" salah dikira ticker.

**Perbaikan:**
- Modul baru `backend/utcp/stock_universe.py` memuat `Daftar Saham - 20261004.csv`
  (962 emiten IDX) sebagai tabel lookup lokal (`exists`, `company_name`,
  `resolve_ticker`, `unknown_ticker_like`).
- Daftar singkatan finansial (`NON_TICKER_WORDS`: EPS, ROE, PER, PBV, LDR, dll)
  dikecualikan agar tidak dianggap ticker.
- Validasi ticker kini **offline** (tanpa API/token). Ticker tak terdaftar
  (mis. `ZZZZ`) ditolak dengan pesan jelas, **0 tool call**.
- Intent detector memakai `stock_universe.resolve_ticker()` sebagai sumber
  kebenaran ticker.

**Verifikasi:** `tests_fast.py` kini **31/31 lulus** (5 cek CSV-gate baru:
universe loaded 962, BBCA exists, ZZZZ tidak, "EPS" bukan ticker, resolve BBCA
dari teks, deteksi ticker-like tak dikenal). Analisis BBCA tetap berfungsi,
tanpa regresi.

---

## 13. Tool Scraping Makro (2026-10-04, sesi lanjutan)

Ditambahkan tiga tool scraping untuk melengkapi `macro_intelligence` dengan
data makro nyata, menggantikan mode market-proxy murni.

### 13.1 Modul & sumber

`backend/utcp/macro_scraper.py` — semua sumber **publik & keyless**:

| Fungsi | Sumber | Data |
|---|---|---|
| `fetch_macro_indicators()` | World Bank Open Data API + exchangerate-api (open.er-api.com) | Inflasi tahunan (CPI %), suku bunga riil (%), kurs USD/IDR |
| `fetch_macro_news_id()` | Antara (ekonomi) / Google News RSS (id) | Berita makro/ekonomi Indonesia |
| `fetch_macro_news_global()` | Google News RSS (global) | Berita makro global (Fed, inflasi, komoditas, kurs) |

### 13.2 Tool UTCP baru

`get_macro_indicators`, `search_macro_news_id`, `search_macro_news_global`
didaftarkan di `TOOL_SPECS` (flag `scraper:true`) dan di `manual.json`.
`facts_extractor.extract_macro_indicators()` memetakan indikator ke Fact Ledger
(tiap fakta membawa `source` + `as_of`).

### 13.3 Kepatuhan grounding

- **BI Rate tetap jujur**: tidak ada sumber numerik keyless yang tepercaya,
  jadi `bi_rate` selalu masuk daftar `unavailable`. Pertanyaan BI Rate dijawab
  dengan konteks makro nyata (inflasi/kurs) **plus** pernyataan jujur bahwa
  angka BI Rate tidak tersedia + rujukan ke bi.go.id.
- Setiap indikator numerik membawa **sumber + tanggal**; angka tetap dirender
  dari penanda `{{f_xxx}}` dan melewati Number Validator.
- Kegagalan jaringan → `empty`/`error`, tidak pernah mengarang nilai.

### 13.4 Routing

`macro_intelligence` dinaikkan ke versi `1.1.0` (tools makro ditambahkan).
Orchestrator kini punya **jalur makro**: intent `macro` atau permintaan angka
makro → menjalankan `macro_intelligence` dengan `get_macro_indicators` +
berita ID & global (tanpa perlu ticker).

### 13.5 Verifikasi

`tests_fast.py` → **38/38 lulus** (7 cek makro baru: inflasi & USD/IDR
bersumber, BI Rate jujur tak tersedia, tiap indikator punya source+as_of,
berita ID & global terambil, tool `get_macro_indicators` → ok). End-to-end:
"Bagaimana inflasi dan kurs Indonesia?" → inflasi 1.91% (2025), suku bunga riil
5.99%, USD/IDR Rp17.889 — semua grounded dari World Bank/er-api. "Berapa BI
Rate?" → konteks makro nyata + penolakan jujur angka BI Rate.

---

## 14. Sumber BPS & Pencarian Berita Bebas (2026-10-04, sesi lanjutan)

### 14.1 BPS sebagai sumber inflasi (key-optional)

Ditambahkan `fetch_bps_inflation()` di `backend/utcp/macro_scraper.py` memakai
**BPS WebAPI** (`webapi.bps.go.id`).

- BPS WebAPI mewajibkan API key. Konfigurasi via `.env`:
  ```env
  BPS_API_KEY=xxxxxxxx          # key gratis dari webapi.bps.go.id/developer
  BPS_INFLATION_VAR=2212        # opsional, var inflasi (default 2212)
  ```
- **Perilaku key-optional:** jika `BPS_API_KEY` ada → BPS menjadi sumber inflasi
  utama (lebih resmi); jika tidak ada → otomatis fallback ke **World Bank**.
  Tidak pernah gagal/mengarang; tetap patuh grounding.
- `get_macro_indicators` kini mengutamakan BPS → World Bank untuk inflasi.
- **BI Rate** tetap `unavailable` secara jujur: BPS menyediakan inflasi, bukan
  suku bunga acuan BI. Pertanyaan BI Rate dijawab dengan konteks makro nyata +
  penolakan jujur angka BI Rate.

### 14.2 Tool pencarian berita bebas (versatile)

Tool baru `search_web_news` + `macro_scraper.search_general_news()`:

- Sumber: **CNN Indonesia RSS** (umum/ekonomi/nasional/internasional/teknologi)
  + **Google News RSS** (query bebas, ID & global).
- Input: `query` (bebas), `scope` (`id`/`global`/`all`), `limit`.
- Memilih kategori CNN relevan dari kata kunci, menggabungkan hasil,
  memberi peringkat berdasarkan kecocokan kata kunci, dan dedup judul.
- Mengembalikan `{title, url, published, summary, source}` — semua **nyata**
  dari feed; tidak ada fabrikasi.

**Jalur orchestrator baru `news_search`:** pertanyaan seperti "cari berita
terbaru tentang harga emas" atau "berita global tentang kebijakan the Fed"
dideteksi (kata: berita/kabar/update/news/...) dan dijalankan oleh
`_run_news_search()`. Jawaban = daftar headline nyata (judul+sumber+tautan) +
ringkasan tematik singkat dari LLM yang **lolos Number Validator** (tanpa angka
karangan); bila ringkasan gagal validasi, daftar judul ditampilkan apa adanya.

### 14.3 Verifikasi

`tests_fast.py` → **43/43 lulus** (5 cek baru: BPS key-optional/fallback,
pencarian berita ID & global mengembalikan hasil, tiap item punya sumber, tool
`search_web_news` → ok). End-to-end:
- "cari berita terbaru tentang harga emas" → `news_search`, 8 headline nyata
  dari CNN/Google News + ringkasan grounded.
- "berita global tentang kebijakan the Fed" → `news_search` scope global.
- BBCA, inflasi, "apa itu EPS" tetap berfungsi tanpa regresi.

### 14.4 Ringkasan tool scraping (total)

| Tool | Sumber | Perlu key? |
|---|---|---|
| `get_macro_indicators` | BPS (opsional) → World Bank + exchangerate-api | tidak (BPS opsional) |
| `search_macro_news_id` | Antara / Google News (id) | tidak |
| `search_macro_news_global` | Google News (global) | tidak |
| `search_web_news` | CNN Indonesia + Google News (query bebas) | tidak |

---

## 15. Perbaikan Kualitas Output Multi-Agent (2026-10-04, sesi lanjutan)

Dari log pengguna ditemukan output rusak pada kueri multi-agent: synthesizer
menarasikan *tentang* data ("data duplikat", "as_of kosong", penanda `{{f_001}}`
mentah) alih-alih menganalisis, berhenti di tengah, dan ada duplikasi fakta.
Empat perbaikan:

### 15.1 Tool `get_time` (konteks waktu)
`backend/utcp/clock.py` + tool UTCP `get_time` mengembalikan tanggal/waktu WIB.
Konteks waktu disuntikkan ke prompt agent dan synthesizer sehingga model
menalar kebaruan data (tidak lagi bingung soal tahun data).

### 15.2 De-duplikasi fakta (Fact Ledger)
`FactLedger.add()` kini mengindeks `(metric, value, unit, as_of)`. Fakta
identik (mis. `last_close_price` dari overview + valuation + daily, atau ledger
multi-agent yang digabung) dikembalikan sebagai fakta yang sama, bukan
duplikat. Terverifikasi: BBCA 18→17 fakta, 0 metrik terduplikasi.

### 15.3 Synthesizer tidak lagi "berhenti tengah jalan"
- Prompt synthesizer ditulis ulang: bekerja dari **narasi agent yang sudah
  dirender** (angka nyata), DILARANG membahas struktur data (duplikat/as_of/
  fact_id), WAJIB analisis substantif dengan struktur Ringkasan/Fundamental/
  Makro/Risiko-Katalis/Kesimpulan/Keterbatasan, dan tidak berhenti di tengah.
- Validasi angka synthesizer diubah: alih-alih menolak semua digit (yang keliru
  memicu fallback karena narasi sudah berisi angka nyata), kini memeriksa bahwa
  synthesizer **tidak menambah angka di luar** yang ada pada narasi agent
  (`_numbers_in` subset check). Angka karangan → fallback gabungan narasi.
- Prompt agent diberi instruksi "berpikir dari data yang tersedia, jangan
  berhenti karena data tak lengkap; sebut kekurangan di keterbatasan".

### 15.4 Auto-fallback ke berita saat tool gagal
`AgentRunner._news_fallback()`: bila No-Data Gate gagal (tool utama error/
kosong, mis. API error), agent otomatis memanggil `search_web_news` untuk
ticker/kueri dan menyajikan berita terbaru nyata (status `partial`,
`agent_id=news_fallback`) alih-alih buntu. Grounded: hanya headline dari tool,
tanpa angka karangan.

### 15.5 Verifikasi
- Kueri log ("kondisi ekonomi Indonesia + analisis BBCA fundamental/makro/
  katalis") kini menghasilkan **analisis multi-agent yang menyatu** (Ringkasan→
  Kesimpulan), tanpa meta-commentary, tanpa penanda mentah, tanpa duplicate
  tool call. Angka dirender: inflasi 1.91%, ROE 20.43%, LDR 78.34%, dll.
- API key dikosongkan → agent fallback ke berita BBCA nyata.
- `tests_fast.py` → **49/49 lulus** (6 cek baru: get_time, dedup fakta, news
  fallback). Tanpa regresi.

---

## 16. Penggantian Tool Sektor 404 dengan Yahoo Finance (2026-10-07, sesi lanjutan)

Permintaan: uji ulang UTCP terhadap Sectors API; untuk endpoint yang 404,
hapus perilaku "tidak tersedia" dan gantikan dengan fitur setara di yfinance.

### 16.1 Hasil uji ulang live API Sectors

Probe langsung (semua tool dipanggil nyata untuk ticker `BBCA`) memastikan
status tier key saat ini:

| Tool | Endpoint | Status |
|---|---|---|
| `get_company_report` (overview/valuation/financials/dividend/**ownership**/**peers**) | `company/report` | ✅ HTTP 200 |
| `get_daily_price` | `daily/{sym}` | ✅ 200 (22 baris) |
| `get_company_corporate_actions` | `company/corporate-actions` | ✅ 200 |
| `search_idx_news` | `news/` | ✅ 200 |
| `get_filings` | `filings/` | ✅ 200 |
| `get_foreign_flow` | `foreign-flow/{sym}` | ✅ 200 |
| `get_idx_total` | `idx-total/` | ✅ 200 |
| `get_index_daily` | `index-daily/{idx}` | ✅ 200 |
| `screen_companies` | `companies/` | ✅ 200 (50 baris) |
| **`get_company_quarterly`** | `company/quarterly/{sym}` | ❌ **HTTP 404** |
| **`get_shareholders`** | `company/shareholders/{sym}` | ❌ **HTTP 404** |

Catatan: section `ownership` dan `peers` pada `company/report` kini **200**
(sebelumnya diperlakukan sebagai tak tersedia). Hanya dua endpoint dedicated
yang tetap 404.

### 16.2 Penggantian dengan yfinance (`backend/utcp/yf_client.py`)

Dua tool yang 404 **tidak lagi** dibiarkan `available:false`. Keduanya kini
mengambil data setara dari **Yahoo Finance** (`yfinance==1.7.0`) untuk ticker
IDX (otomatis menambah suffix `.JK`):

| Tool UTCP | Sumber yfinance | Field |
|---|---|---|
| `get_company_quarterly` | `quarterly_income_stmt` + `quarterly_balance_sheet` | revenue, earnings, net_interest_income, total_equity, total_assets, total_debt, eps |
| `get_shareholders` | `major_holders` + `institutional_holders` | insider %, institusi %, institutional float %, jumlah institusi |

Catatan versi: `yfinance==0.2.51` (lama) rate-limited/kembali kosong untuk
IDX; **1.7.0** + `curl_cffi==0.16.3` bekerja. Keduanya ditambahkan ke
`requirements.txt`.

### 16.3 Perubahan kode

- `backend/utcp/yf_client.py` (baru): `fetch_quarterly()`, `fetch_shareholders()`,
  `_yf_symbol()`. Transport murni; mengembalikan `dict` nyata atau `None`
  (gagal/kosong). Tidak pernah mengarang nilai.
- `backend/utcp/registry.py`: `TOOL_SPECS` dua tool → `available:true`,
  `source:"yfinance"`; `_t_get_company_quarterly`/`_t_get_shareholders` ditulis
  ulang memakai `yf_client`, membungkus hasil via `ok/empty/error` (envelope UTCP
  tetap seragam, No-Data Gate tetap bekerja bila yfinance kosong).
- `backend/runtime/facts_extractor.py`: `extract_quarterly()` (fakta `q_*` +
  ROE kuartalan tahunan turunan) dan `extract_shareholders()` (ownership %).
  Setiap fakta membawa `field_path` bersumber `yfinance.*`.
- `backend/runtime/agent_runner.py`: `_extract()` merutekan payload yfinance ke
  dua extractor baru.
- `backend/grounding/sanity_checks.py`: rentang wajar untuk `q_roe_annualized`
  dan metrik kepemilikan (0–100%).
- `backend/utcp/manual.json`: dua tool ditandai `available:true` + `source:yfinance`.

### 16.4 Kepatuhan grounding dipertahankan

- Angka yfinance **tetap** fakta ber-`evidence_id` + sumber "Yahoo Finance",
  lolos sanity-check, dirender via penanda `{{f_xxx}}` → Number Validator.
- Kegagalan jaringan / rate limit → `empty`/`error`; No-Data Gate tetap jujur.
- Nama tool tidak berubah → whitelist Agent Factory & spec agent tidak perlu
  diubah (hanya implementasi tool yang diganti).

### 16.5 Verifikasi

- Probe live: `get_company_quarterly` & `get_shareholders` → `ok` dengan data
  BBCA nyata (kuartal `2026-06-30`: NII Rp21.94 T, laba Rp14.85 T, ekuitas
  Rp270.44 T; kepemilikan insider 60.81%, institusi 19.53%, 376 institusi).
- Ekstraksi fakta: 11 fakta bersih (7 kuartalan + 4 kepemilikan), nol anomali,
  `q_roe_annualized=21.96%`.
- End-to-end `fundamental_analyst` BBCA: keempat tool `ok` (termasuk dua
  yfinance), **28 fakta semua ber-`evidence_id`**, identity=bank, confidence 1.0,
  tanpa tool call ganda. Fakta kuartalan yfinance melengkapi data tahunan Sectors.
- `tests_fast.py` → **59/59 lulus** (10 cek yfinance baru: dua tool kini
  `available`, yfinance importable, quarterly/shareholders → `ok` bersumber
  Yahoo Finance, fakta terekstraksi tanpa anomali). Satu test news-fallback
  diubah memakai `investment_guide` (Sectors-only): karena `fundamental_analyst`
  kini punya tool yfinance yang independen dari Sectors key, mengosongkan key
  Sectors tidak lagi memicu no-data (sistem lebih tahan = benar).


---

## 17. Web Card Interface & Presentation Composer (2026-10-07, sesi lanjutan)

Mengikuti `PRD_AISector-MoGent_Web-Cards_v1.0.md`. Output analisis kini dapat
disajikan sebagai **deck kartu geser** di website React, bukan hanya teks
panjang. Satu base agent baru — **Presentation Composer** — menyusun kartu dari
fakta tervalidasi (tanpa menganalisis ulang, tanpa membuat angka). Backend
diperluas, bukan diubah: pipeline grounding, Agent Factory, dan integritas base
agent tetap berlaku.

Status akhir sesi: **backend `tests_fast.py` 70/70 lulus**, **frontend
`npm run build` sukses**, **`/cards` dan `/query` terverifikasi live**.

### 17.1 Agent baru: `presentation_composer` (base, immutable)

`data/agents/base/presentation_composer.json` — base agent ke-9. Menambah blok
baru `presentation` pada skema agent (opsional, hanya untuk kartu):

```json
"presentation": {
  "card_order": ["summary","valuation","performance","ownership","macro","price","chart","news","risk","trace"],
  "density": "normal",            // compact | normal | detailed
  "explain_level": "simple",      // simple | standard | expert
  "font_scale": 1.0,
  "glossary_hints": false,
  "max_facts_per_card": 8
}
```

- `tools: []` — tidak memanggil tool data.
- `locked_constraints`: `GROUNDING_V1`, `NO_FABRICATION`, `NO_TRADE_EXECUTION`.
- Terdaftar di `registry.json` dengan `sha256` → tunduk pemeriksaan integritas
  base agent (startup berhenti bila file diubah manual — W-T14).
- Jumlah base agent: **8 → 9** (tidak ada base lama yang berubah/terhapus).

### 17.2 Ekspansi kontrak `/query` (W0, PRD Web-Cards 9.1)

Respons `/query` kini mengekspos data yang sebelumnya hanya ada di dalam
pipeline, agar kartu dapat dibangun:

- `facts[]` — fakta global ter-dedup dari seluruh agent output (membawa
  `fact_id`, `metric`, `value`, `unit`, `as_of`, `evidence_id`, `field_path`,
  `derived`, `formula`, `anomaly`, `source`).
- `evidence[]` — satu record per tool call; **payload mentah hanya disertakan
  untuk tool kartu** (`get_daily_price`, berita, `get_macro_indicators`) agar
  respons tetap ramping (PRD risk #2).
- `ticker`, `persona`, `agent_factory` — selalu ada di respons dasar.

Implementasi:
- `backend/runtime/agent_runner.py`: konstanta `PAYLOAD_TOOLS` + helper
  `build_evidence_public()`; setiap output agent (success/no_data/news_fallback)
  kini membawa `evidence`.
- `backend/orchestrator/orchestrator.py`: `_expose_facts_evidence()` (dipanggil
  dari `_finalize_tools`) menggabungkan fakta ter-dedup (`fact_id` lalu
  `metric/value/unit/as_of`) dan membangun `evidence` dari `RequestCache`;
  `_source_label()` memetakan `field_path` → label sumber (Sectors / Yahoo
  Finance / Makro BPS·World Bank).

### 17.3 Modul backend baru (`backend/presentation/`)

| Berkas | Fungsi |
|---|---|
| `card_builder.py` | **Deterministik** fakta → kartu. `METRIC_LABEL` (label ID baku), `CARD_METRICS` (pengelompokan summary/valuation/performance/ownership/price), kartu makro via `field_path`, kartu `chart` dari payload `get_daily_price` (butuh ≥ 5 titik — W-T9), kartu `news` dari payload tool berita, dedup `(metric,value,as_of)` (W-T2), anomali tidak ditampilkan sebagai angka (ke `trace` — W-T4), kartu `trace` **selalu terakhir** berisi agent dipakai, tool berhasil/gagal, info Agent Factory, keterbatasan, kontradiksi, disclaimer (W3). |
| `explain.py` | Lapisan penjelasan **tanpa LLM** (MVP): glosarium statis (PER/PBV/ROE/LDR/dst) + kalimat dari sintesis tervalidasi, disaring dari **penilaian tanpa dasar** ("tinggi/mahal/sehat" tanpa pembanding — PRD 7.4/W-T7), **frasa meta** ("narasi agent", "tidak terdapat kontradiksi", `fact_id`, penanda `{{f_}}` — W-T8), dan kata perintah beli/jual. |
| `profiles.py` | Resolusi blok `presentation`. Menjamin `trace` selalu ada & terakhir, `max_facts_per_card ≤ 8`, `font_scale` di-clamp, jumlah bullet dari `density`. |
| `routes.py` | `POST /cards` — stateless, **tanpa LLM**. Body = hasil `/query`; memilih profil penyajian dari agent turunan ber-blok `presentation` bila ada, selain itu `presentation_composer` dasar. |

Nilai angka pada kartu dirender oleh **formatter yang sama** dengan Fact Ledger
(`backend.grounding.fact_ledger.format_value`), sehingga nilai di kartu identik
dengan nilai di teks (PRD 13). Tidak ada angka yang dibuat di lapisan kartu.

### 17.4 Integrasi Agent Factory (W4, PRD Web-Cards 8)

Presentation Composer dapat digabung/dimodifikasi seperti agent lain, **tanpa
mengubah aslinya**:

- `backend/agent_factory/merge_rules.py`: `presentation` ditambahkan ke
  `MODIFY_ALLOWED`; `apply_overrides()` melakukan **deep-merge** blok
  presentation (bukan menimpa); `compose()` membawa blok presentation dari induk.
- `backend/agent_factory/factory.py`: cabang MODIFY menyalin
  `parent.presentation`.
- `backend/agent_factory/validator.py`: menolak agent turunan bila
  `presentation.card_order` tidak menyertakan `trace` (W-T10) atau
  `max_facts_per_card > 8` (W4).

Contoh profil turunan (dibuat otomatis bila persona terdeteksi; induk tetap
utuh): `derived_cards_beginner` (`explain_level=simple`, glosarium),
`derived_cards_senior` (`font_scale=1.25`, `risk` di depan, `density=compact`),
`derived_cards_macro` (`macro`/`news` di depan).

### 17.5 Endpoint API

`backend/api.py` memasang router `/cards` dan membagikan registry orchestrator
ke router saat startup (`cards_routes.set_registry`).

| Endpoint | Metode | Fungsi |
|---|---|---|
| `/query` | POST | Sudah ada; diperluas (17.2) |
| `/cards` | POST | **Baru.** Body = hasil `/query`; respons = skema kartu (PRD 9.2) |
| `/agents`, `/agents/{id}/lineage` | GET | Sudah ada |

Skema kartu respons:

```json
{
  "cards": [
    { "id":"valuation","type":"metrics","title":"Valuasi & Dividen",
      "subtitle":"opsional",
      "facts":[{"label":"PER","value":"22,40x","as_of":"2026-09-30",
                "source":"Sectors","evidence_id":"ev_0007","derived":false,"formula":null}],
      "bullets":["..."], "items":[{"title":"...","source":"...","date":"...","url":"..."}],
      "series":[{"d":"2026-09-07","c":6050}] }
  ],
  "meta": { "agent":"presentation_composer@1.0.0","n_facts":17,"profile":"default",
            "font_scale":1.0,"density":"normal" }
}
```

### 17.6 Frontend React (`frontend/`)

Stack: **Vite 5 + React 18 + TypeScript + Tailwind CSS 4.1.13** (struktur ala
shadcn: komponen di `src/components/ui/`, util `cn` di `src/lib/utils.ts`).
Tema **minimalis** (ink-on-paper, garis rambut, aksen near-black, whitespace
lega).

Struktur:

```text
frontend/
├── index.html
├── package.json            # dev: npm run dev (5173); build: tsc --noEmit && vite build
├── vite.config.ts          # @vitejs/plugin-react + @tailwindcss/vite, alias @ -> src
├── tsconfig.json
├── .env.example            # VITE_API=http://localhost:8000
└── src/
    ├── main.tsx
    ├── App.tsx             # alur: /query -> (jika Mode Kartu) /cards; loading; error; empty state
    ├── index.css           # Tailwind 4 @theme (token minimalis), scroll-snap deck, keyframes
    ├── types.ts            # tipe Card/CardFact/NewsItem/SeriesPoint/CardsResponse/QueryResult
    ├── vite-env.d.ts
    ├── lib/{utils.ts, api.ts}   # cn(); runQuery()/buildCards() memakai VITE_API
    └── components/ui/
        ├── QueryBar.tsx        # input + tool ▦ Mode Kartu (aria-pressed, default ON) + Analisis
        ├── LoadingSteps.tsx    # orb pulsing minimalis + label bertahap (homage MorphOrb)
        ├── Deck.tsx            # scroll-snap, tombol ‹ ›, titik indikator (role=tab), keyboard, aria-live
        ├── Card.tsx            # render per tipe + animasi masuk (motion)
        ├── FactGrid.tsx        # grid fakta; klik info -> sumber/evidence_id/rumus (ƒ)
        ├── Sparkline.tsx       # grafik harga SVG murni (tanpa lib chart)
        ├── NewsList.tsx        # daftar berita (judul/sumber/tanggal/tautan)
        ├── Bullets.tsx         # butir penjelasan/risiko
        ├── TracePanel.tsx      # Sumber & Keterbatasan; tool gagal (teks + ✗, bukan warna saja)
        └── PlainAnswer.tsx     # mode teks (Mode Kartu OFF)
```

Perilaku kunci (PRD 6, 11):
- **Tool ▦ Mode Kartu** default ON. ON → `POST /query` lalu `POST /cards`;
  OFF → hanya `/query` (teks). Satu klik untuk berpindah.
- **Deck** dapat digeser (sentuh/trackpad), tombol ‹ ›, titik indikator yang
  dapat diklik, panah keyboard (**dinonaktifkan saat fokus di input** — W-T19),
  kartu aktif diumumkan via `aria-live` (W-T20). Lebar kartu `min(520px, 86vw)`.
- Setiap fakta membawa `evidence_id`/sumber; klik ikon info membuka detail bukti.
  Fakta turunan ditandai **(ƒ)** + rumus. Fakta tanpa `as_of` → "tanggal tidak
  tercantum".
- **Degradasi anggun** (PRD 11.5): backend tak terjangkau → pesan di bawah
  input, deck lama dipertahankan; `/query` sukses tapi `/cards` gagal → tampilkan
  teks + "Mode Kartu gagal, menampilkan teks" (W-T17); tanpa fakta terstruktur →
  kartu berbasis teks + `trace`.
- Aksesibilitas: target sentuh tombol navigasi ≥ 44 px, status ✓/✗ disertai
  teks (bukan warna saja), lebar minimal 360 px, `prefers-reduced-motion`
  dihormati.

Alamat API dikonfigurasi via `VITE_API` (default `http://localhost:8000`).

### 17.7 Perubahan berkas backend (ringkas)

| Berkas | Perubahan |
|---|---|
| `backend/runtime/agent_runner.py` | `PAYLOAD_TOOLS`, `build_evidence_public()`, field `evidence` di semua output |
| `backend/orchestrator/orchestrator.py` | default `facts`/`evidence`/`ticker`; `_expose_facts_evidence()`, `_source_label()` |
| `backend/presentation/` (baru) | `card_builder.py`, `explain.py`, `profiles.py`, `routes.py`, `__init__.py` |
| `backend/agent_factory/merge_rules.py` | `presentation` di `MODIFY_ALLOWED`; deep-merge; propagasi via compose |
| `backend/agent_factory/factory.py` | cabang MODIFY menyalin `parent.presentation` |
| `backend/agent_factory/validator.py` | validasi blok presentation (trace wajib, max_facts ≤ 8) |
| `backend/api.py` | pasang router `/cards`, bagikan registry saat startup |
| `data/agents/base/presentation_composer.json` (baru) | base agent ke-9 |
| `data/agents/registry.json` | entri + `sha256` presentation_composer |
| `tests_fast.py` | base count 8→9; +11 cek Web-Cards |

### 17.8 Verifikasi

**Backend — `python tests_fast.py` → 70/70 lulus** (59 lama + 11 cek Web-Cards
baru):
- `presentation_composer` adalah base dan punya blok `presentation`.
- W-T1 kartu `trace` selalu terakhir.
- W-T2 fakta LDR duplikat menyusut jadi 1.
- W-T4 anomali tidak tampil sebagai angka (muncul di `trace`).
- W-T5 tool gagal tercantum di `trace`.
- W-T7/W-T8 kata penilaian ("tinggi") & frasa meta ("tidak terdapat
  kontradiksi") tidak bocor ke bullet.
- W-T6 tanpa fakta → kartu teks + `trace`.
- W-T9 payload harga < 5 titik → kartu `chart` tidak dibuat.
- W-T10 `card_order` tanpa `trace` ditolak Factory; `max_facts_per_card > 8`
  ditolak.

**Live `/cards`** (FastAPI, tanpa LLM) dari hasil `/query` sintetis: skema kartu
valid, nilai terformat (`Rp10.200`, `22.40x`, `78.34%`), LDR turunan ber-(ƒ) +
rumus, kata "tinggi" tersaring dari bullet, judul ringkasan dari identity.

**Live end-to-end** (`/query` BBCA → `/cards`, pipeline nyata + Ollama):
- `/query`: status `success`, **28 fakta semuanya ber-`evidence_id` + sumber**
  (nol angka tanpa sumber — W-T3), 4 evidence.
- `/cards`: 8 kartu (`summary, valuation, performance, ownership, price, risk,
  glossary, trace`), `trace` terakhir, **0 fakta tanpa sumber/evidence**; kartu
  `chart` benar tidak dibuat karena `fundamental_analyst` tak punya tool harga.

**Frontend — `npm run build`**: `tsc --noEmit` + `vite build` sukses
(≈ 298 kB JS / 20 kB CSS, gzip ≈ 96 kB / 4.8 kB).

**Integritas**: registry OK, 9 base agent (termasuk `presentation_composer`
dengan `sha256` terkunci), base agent tidak berubah.

### 17.9 Cara menjalankan (frontend)

```bash
# backend (seperti biasa)
uvicorn backend.api:app --reload --port 8000

# frontend
cd frontend
npm install
cp .env.example .env        # set VITE_API bila API tidak di localhost:8000
npm run dev                 # http://localhost:5173
# build produksi:
npm run build               # output ke frontend/dist
```

### 17.10 Pemetaan temuan `output_log.md` → solusi kartu

| Temuan output | Solusi |
|---|---|
| Teks panjang satu blok | Deck kartu (17.6) |
| Hanya 3 fakta tampil dari 14 tool | Grid fakta per kelompok dari ledger (17.3) |
| "LDR Hitung" 3× | Dedup `(metric,value,as_of)` (W-T2) |
| "LDR 78,34% tinggi" | Aturan penilaian tanpa dasar disaring (7.4/W-T7) |
| "Tidak terdapat kontradiksi dalam narasi agent" | Filter frasa meta (W-T8) |
| Jejak agent & tool gagal terkubur | Kartu `trace` wajib & terakhir (W3) |
| Berita tidak terstruktur | Kartu `news` dari payload tool berita |
