# Sectors Financial API --- IDX API v2

> Dokumentasi referensi praktis untuk **Indonesia Stock Exchange (IDX)**
> menggunakan Sectors Financial API v2.
>
> Sumber resmi: https://docs.sectors.app/
>
> Base URL: `https://api.sectors.app/v2`

## 1. Overview

Sectors Financial API menyediakan data pasar dan riset saham Indonesia,
termasuk:

-   Informasi perusahaan IDX
-   Fundamental dan laporan keuangan
-   Valuasi
-   Dividend
-   Ownership dan management
-   Harga dan transaksi harian
-   IDX market capitalization
-   Index
-   News dan company filings
-   Corporate actions
-   Broker activity
-   Foreign flow
-   Stock screener
-   Ranking dan market movers

Dokumentasi ini menggunakan **API v2**.

------------------------------------------------------------------------

## 2. Authentication

Semua endpoint membutuhkan API key.

Header:

``` http
Authorization: YOUR_SECTORS_API_KEY
```

Contoh:

``` bash
curl --request GET \
  --url https://api.sectors.app/v2/company/report/BBCA/ \
  --header "Authorization: ${SECTORS_API_KEY}"
```

### `.env`

Disarankan menyimpan API key di environment variable:

``` env
SECTORS_API_KEY=your_api_key_here
```

Jangan memasukkan API key ke:

-   source code yang di-commit
-   frontend/browser
-   GitHub repository
-   prompt LLM
-   response AI yang ditampilkan ke user

------------------------------------------------------------------------

## 3. IDX Symbol

Format simbol IDX:

``` text
BBCA
BBRI
BMRI
TLKM
GOTO
```

`.JK` juga dapat digunakan pada endpoint yang mendukungnya:

``` text
BBCA.JK
```

Umumnya input symbol bersifat case-insensitive.

------------------------------------------------------------------------

# 4. API Categories

  Category               Kegunaan
  ---------------------- ----------------------------------------------------
  Screener               Mencari/filter perusahaan IDX
  Company Report         Fundamental, valuation, dividend, ownership, peers
  Quarterly Financials   Data keuangan kuartalan
  Transaction            Harga/transaksi harian
  Market                 Total market cap IDX
  Index                  Data indeks IDX
  Ranking                Top movers dan most traded
  News                   Berita IDX
  Filings                Transaksi insider/investor
  Corporate Actions      Dividen, rights issue, stock split, dll.
  Broker                 Aktivitas broker
  Foreign Flow           Net foreign buy/sell
  Helper                 Taxonomy, tags, tanggal laporan

------------------------------------------------------------------------

# 5. Company Screener

## Endpoint

``` http
GET /v2/companies/
```

Full URL:

``` text
https://api.sectors.app/v2/companies/
```

Screener mendukung:

1.  Structured query menggunakan `where`
2.  Sorting menggunakan `order_by`
3.  Natural-language query menggunakan `q`

Structured query menggunakan **1 API credit**.

Natural-language query menggunakan **3 API credits**.

### Contoh

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/companies/?where=market_cap%3E10000000000000&order_by=-market_cap" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

### Natural language

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/companies/?q=large%20Indonesian%20banks" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

### Konsep filter

Screener dapat digunakan untuk mencari perusahaan berdasarkan atribut
seperti:

-   symbol
-   company name
-   sector
-   subsector
-   industry
-   sub-industry
-   market cap
-   valuation
-   financial metrics
-   growth
-   dividend
-   ownership
-   free float
-   management

Contoh kebutuhan AI Agent:

``` text
Cari perusahaan IDX sektor Energy dengan market cap > Rp10T
dan revenue growth positif.
```

Screener adalah endpoint yang cocok untuk kebutuhan tersebut.

------------------------------------------------------------------------

# 6. Company Report

## Endpoint

``` http
GET /v2/company/report/{symbol}/
```

Contoh:

``` text
https://api.sectors.app/v2/company/report/BBCA/
```

### Sections

Company Report terdiri dari:

  -----------------------------------------------------------------------
  Section                             Isi
  ----------------------------------- -----------------------------------
  `overview`                          Identitas perusahaan, market cap,
                                      harga, ESG, tags, index

  `valuation`                         PE, PB, PS, PCF, PEG, intrinsic
                                      value

  `future`                            Forecast EPS/revenue dan analyst
                                      rating

  `peers`                             Peer comparison

  `financials`                        Historical financial statements dan
                                      ratios

  `dividend`                          Dividend history, yield, payout

  `management`                        Executive dan shareholding

  `ownership`                         Major shareholders dan ownership
  -----------------------------------------------------------------------

Secara default seluruh section dikembalikan.

### Memilih section

Jika hanya membutuhkan valuation:

``` text
GET /v2/company/report/BBCA/?sections=valuation
```

Jika membutuhkan fundamental + valuation:

``` text
GET /v2/company/report/BBCA/?sections=financials,valuation
```

Pemilihan section penting untuk AI Agent karena dapat mengurangi
response size dan API credit.

### Response sederhana

``` json
{
  "symbol": "BBCA.JK",
  "company_name": "PT Bank Central Asia Tbk.",
  "overview": {},
  "valuation": {},
  "future": {},
  "financials": {},
  "dividend": {},
  "management": {},
  "ownership": {},
  "peers": []
}
```

### Contoh Python

``` python
import os
import requests

url = "https://api.sectors.app/v2/company/report/BBCA/"
headers = {
    "Authorization": os.getenv("SECTORS_API_KEY")
}

response = requests.get(url, headers=headers)
response.raise_for_status()

data = response.json()

print(data["valuation"])
```

------------------------------------------------------------------------

# 7. Daily Transaction Data

## Endpoint

``` http
GET /v2/daily/{symbol}/
```

Contoh:

``` text
https://api.sectors.app/v2/daily/BBCA/
```

Data mencakup:

-   date
-   open
-   high
-   low
-   close
-   volume
-   market cap

### Query parameters

``` text
start=YYYY-MM-DD
end=YYYY-MM-DD
```

Default:

-   sekitar 30 hari terakhir
-   maksimum window 90 hari

Contoh:

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/daily/BBCA/?start=2026-09-01&end=2026-09-30" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

### Response

``` json
[
  {
    "symbol": "BBCA.JK",
    "date": "2026-09-30",
    "open": 8000,
    "high": 8100,
    "low": 7950,
    "close": 8050,
    "volume": 92219000,
    "market_cap": 1095329638012500
  }
]
```

------------------------------------------------------------------------

# 8. Daily Full-Universe Close

## Endpoint

``` http
GET /v2/close/
```

Digunakan untuk mengambil harga penutupan **seluruh ticker IDX pada satu
tanggal**.

Ini lebih efisien daripada memanggil `/daily/{symbol}/` untuk setiap
ticker.

Use case:

-   market snapshot
-   screening seluruh saham
-   daily market pipeline
-   AI market overview

------------------------------------------------------------------------

# 9. IDX Market Summary

## Endpoint

``` http
GET /v2/idx-total/
```

Mengambil historical total IDX market capitalization.

Parameter utama:

``` text
start=YYYY-MM-DD
end=YYYY-MM-DD
```

Window maksimal: 90 hari.

Contoh:

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/idx-total/?start=2026-09-01&end=2026-09-30" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

------------------------------------------------------------------------

# 10. Index Daily Transaction

## Endpoint

``` http
GET /v2/index-daily/{index}/
```

Mengambil historical closing level suatu IDX index.

Contoh index:

``` text
IDX30
LQ45
IDXHIDIV20
IDXQ30
IDXV30
IDXG30
```

Parameter:

``` text
start=YYYY-MM-DD
end=YYYY-MM-DD
```

------------------------------------------------------------------------

# 11. Daily Full-Universe Index Close

## Endpoint

``` http
GET /v2/index-daily-universe/
```

Mengambil closing level **seluruh IDX index pada satu trading day**.

Cocok untuk:

-   market dashboard
-   market breadth
-   comparison antar-index
-   macro/market agent

------------------------------------------------------------------------

# 12. Quarterly Financials

## Endpoint

``` http
GET /v2/company/quarterly/{symbol}/
```

Parameter:

  Parameter       Type      Keterangan
  --------------- --------- ------------------------------
  `report_date`   string    Tanggal laporan `YYYY-MM-DD`
  `approx`        boolean   Approximate quarter matching
  `n_quarters`    integer   Jumlah quarter terbaru

Contoh:

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/company/quarterly/BBCA/?n_quarters=8" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

Field umum:

``` text
revenue
earnings
total_assets
total_equity
operating_cash_flow
gross_profit
operating_expense
provision
earnings_before_tax
tax
total_liabilities
total_debt
financing_cash_flow
investing_cash_flow
net_cash_flow
free_cash_flow
```

Field tambahan dapat tersedia berdasarkan sektor.

Untuk bank/financial sector dapat muncul metrik seperti:

``` text
net_interest_income
gross_loan
total_deposit
```

------------------------------------------------------------------------

# 13. Quarterly Financial Dates

## Endpoint

``` http
GET /v2/company/quarterly-dates/{symbol}/
```

Digunakan untuk mendapatkan daftar tanggal laporan kuartalan yang
tersedia.

Workflow yang direkomendasikan:

``` text
Quarterly Financial Dates
        ↓
ambil report_date valid
        ↓
Quarterly Financials
        ↓
analisis QoQ / YoY
```

------------------------------------------------------------------------

# 14. Company Revenue Segments

## Endpoint

``` http
GET /v2/company/segments/{symbol}/
```

Mengambil breakdown revenue dan cost segment berdasarkan tahun
finansial.

Tidak semua perusahaan memiliki segment data.

Gunakan endpoint **Companies with Revenue Segments** terlebih dahulu
untuk mengecek coverage.

------------------------------------------------------------------------

# 15. Companies with Revenue Segments

## Endpoint

``` http
GET /v2/company/segments/
```

Digunakan untuk menemukan perusahaan yang mempunyai data revenue/cost
segment beserta financial year yang tersedia.

------------------------------------------------------------------------

# 16. Corporate Actions

## Endpoint

``` http
GET /v2/company/corporate-actions/{symbol}/
```

Digunakan untuk corporate action sebuah perusahaan.

Contoh:

``` text
BBCA
BBRI
BMRI
TLKM
```

Corporate action dapat mencakup event seperti:

-   dividend
-   rights issue
-   stock split
-   bonus
-   buyback
-   merger/acquisition
-   dan corporate action lainnya yang tersedia pada data Sectors.

------------------------------------------------------------------------

# 17. Corporate Actions Calendar

## Endpoint

``` http
GET /v2/corporate-actions/
```

Market-wide counterpart dari endpoint corporate actions per perusahaan.

Gunakan endpoint ini jika agent membutuhkan:

``` text
"Corporate action apa saja minggu ini?"
```

atau:

``` text
"Ada rights issue apa bulan ini?"
```

------------------------------------------------------------------------

# 18. Shareholders Composition

## Endpoint

``` http
GET /v2/company/shareholders/{symbol}/
```

Mengambil komposisi pemegang saham.

Useful fields dapat mencakup:

-   major shareholder
-   share amount
-   share value
-   ownership percentage
-   institutional ownership
-   ownership changes

------------------------------------------------------------------------

# 19. Free Float

## Endpoint

``` http
GET /v2/free-float/
```

Mengambil persentase free float perusahaan IDX.

Dapat difilter berdasarkan taxonomy sektor.

Free float:

``` text
0.45 = 45%
```

------------------------------------------------------------------------

# 20. Industries

## Endpoint

``` http
GET /v2/industries/
```

Mengambil daftar industry/subsector yang tersedia.

Gunakan endpoint ini untuk discovery sebelum membuat query berdasarkan
taxonomy.

------------------------------------------------------------------------

# 21. Subindustries

## Endpoint

``` http
GET /v2/subindustries/
```

Mengambil daftar pasangan industry/sub-industry dalam format slug.

------------------------------------------------------------------------

# 22. Subsectors

## Endpoint

``` http
GET /v2/subsectors/
```

Mengambil daftar sector/subsector.

Gunakan hasil endpoint ini sebagai nilai yang valid untuk parameter:

``` text
sector
sub_sector
```

------------------------------------------------------------------------

# 23. News Tags

## Endpoint

``` http
GET /v2/tags/
```

Mengambil seluruh tag yang tersedia untuk news dan filings.

Contoh penggunaan:

``` text
tags=insider-trading,bullish
```

------------------------------------------------------------------------

# 24. News Articles

## Endpoint

``` http
GET /v2/news/
```

Default data source:

``` text
extension=idx
```

### Parameters

  Parameter     Keterangan
  ------------- -----------------------------
  `start`       Tanggal awal
  `end`         Tanggal akhir
  `limit`       Jumlah item, max 30
  `offset`      Pagination
  `tags`        Comma-separated tags
  `extension`   `idx` atau `mining`
  `keyword`     Substring match pada title
  `symbols`     Comma-separated IDX symbols

Contoh:

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/news/?symbols=BBCA,BBRI&limit=20" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

### Untuk AI Agent

Contoh query:

``` text
Cari berita IDX terkait BMRI dalam 3 hari terakhir.
```

Recommended parameters:

``` text
extension=idx
symbols=BMRI
start=YYYY-MM-DD
end=YYYY-MM-DD
```

------------------------------------------------------------------------

# 25. Company Filings

## Endpoint

``` http
GET /v2/filings/
```

Mengambil IDX insider trading filings.

Parameter penting:

  Parameter            Keterangan
  -------------------- ------------------------------------------------
  `start`              Tanggal awal
  `end`                Tanggal akhir
  `symbol`             Filter ticker
  `sector`             Filter sector
  `sub_sector`         Filter subsector
  `tags`               Filter tags
  `transaction_type`   `buy`, `sell`, `others`
  `holder_type`        `corporate-investor`, `insider`, `institution`
  `limit`              Max 30
  `offset`             Pagination

Contoh:

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/filings/?symbol=BBCA&transaction_type=buy" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

------------------------------------------------------------------------

# 26. Stock Suspensions

## Endpoint

``` http
GET /v2/suspensions/
```

Mengambil historical stock suspension.

Filter:

``` text
symbol
start
end
```

Data dapat digunakan untuk risk analysis:

``` text
"Apakah saham ini pernah terkena suspension?"
```

------------------------------------------------------------------------

# 27. Most Traded Stocks

## Endpoint

``` http
GET /v2/most-traded/
```

Mengambil saham dengan transaction volume terbesar dalam suatu periode.

Date range maksimum: 90 hari.

Use case:

-   liquidity analysis
-   market scanner
-   momentum scanner
-   retail-interest detection

------------------------------------------------------------------------

# 28. Top Company Movers

## Endpoint

``` http
GET /v2/top-changes/
```

Classification:

``` text
top_gainers
top_losers
```

Periods:

``` text
1d
7d
14d
30d
365d
```

Contoh konsep:

``` text
/v2/top-changes/?classification=top_gainers&period=7d
```

------------------------------------------------------------------------

# 29. IPO & Listing Performance

## Endpoint

``` http
GET /v2/ipo/{symbol}/
```

Mengambil performance saham sejak listing.

Window performance:

``` text
7d
30d
90d
365d
```

Useful untuk:

-   IPO analysis
-   post-IPO momentum
-   IPO screening

------------------------------------------------------------------------

# 30. Foreign Flow

## Endpoint

``` http
GET /v2/foreign-flow/{symbol}/
```

Mengambil daily net foreign investor flow untuk satu ticker.

Parameter:

``` text
start=YYYY-MM-DD
end=YYYY-MM-DD
```

Interpretasi:

``` text
net_foreign_inflow > 0
    = foreign net buy

net_foreign_inflow < 0
    = foreign net sell
```

`foreign_share` menunjukkan proporsi foreign terhadap two-sided
turnover.

------------------------------------------------------------------------

# 31. Daily Full-Universe Foreign Flow

## Endpoint

``` http
GET /v2/foreign-flow/
```

Mengambil foreign flow untuk **seluruh IDX ticker pada satu trading
day**.

Lebih efisien daripada memanggil endpoint per-symbol berulang kali.

Cocok untuk:

``` text
foreign flow scanner
market-wide foreign accumulation
AI market sentiment
```

------------------------------------------------------------------------

# 32. Broker Activity by Symbol

## Endpoint

``` http
GET /v2/broker-summary/{symbol}/
```

Mengambil aktivitas broker untuk satu ticker.

Parameter:

  Parameter       Keterangan
  --------------- ------------------------
  `broker_code`   Optional filter broker
  `start`         Start date
  `end`           End date

Default window:

``` text
end = today
start = end - 14 days
```

Contoh:

``` bash
curl --request GET \
  --url "https://api.sectors.app/v2/broker-summary/BBCA/?start=2026-09-20&end=2026-09-30" \
  --header "Authorization: ${SECTORS_API_KEY}"
```

Data dapat berisi:

-   buy value
-   sell value
-   net value
-   lots
-   frequency
-   weighted average price

------------------------------------------------------------------------

# 33. Top Buyers and Sellers per Symbol

## Endpoint

``` http
GET /v2/broker-summary-top/{symbol}/
```

Digunakan untuk melihat broker yang paling banyak:

``` text
net buying
net selling
```

pada suatu saham.

Use case:

``` text
"Broker mana yang paling banyak akumulasi BBCA?"
```

------------------------------------------------------------------------

# 34. Broker Activity by Code

## Endpoint

``` http
GET /v2/broker-activity/{broker_code}/
```

Mengambil seluruh aktivitas trading satu broker.

Date range maksimum:

``` text
14 days
```

Optional:

``` text
symbol
```

Use case:

``` text
"BBCA hari ini banyak ditransaksikan oleh broker apa?"
```

atau:

``` text
"Apa saja saham yang diakumulasi broker tertentu?"
```

------------------------------------------------------------------------

# 35. Top Accumulations and Distributions per Broker

## Endpoint

``` http
GET /v2/broker-activity-top/{broker_code}/
```

Menghasilkan:

``` text
top_accumulations
top_distributions
```

Accumulation:

``` text
positive net IDR
```

Distribution:

``` text
negative net IDR
```

------------------------------------------------------------------------

# 36. Broker Registry

## Endpoint

``` http
GET /v2/broker-registry/
```

Registry broker IDX.

Informasi dapat mencakup:

-   broker code
-   broker name
-   origin
-   cohort
-   license type

Gunakan endpoint ini sebagai sumber validasi broker code sebelum
memanggil broker-scoped endpoint.

------------------------------------------------------------------------

# 37. Top Brokers Daily Ranking

## Endpoint

``` http
GET /v2/brokers/top/
```

Ranking broker berdasarkan:

-   gross trade value
-   absolute net flow

Optional classification:

``` text
origin:
  foreign
  domestic

cohort:
  retail
  mixed
  institutional
  unknown
```

------------------------------------------------------------------------

# 38. Recommended AI Agent Architecture

Untuk AI stock-analysis agent, jangan memberikan seluruh API ke semua
agent.

Gunakan tool grouping.

## Fundamental Agent

Recommended:

``` text
company report
quarterly financials
quarterly financial dates
company segments
shareholders
companies screener
```

Contoh workflow:

``` text
User
  ↓
Orchestrator
  ↓
Fundamental Agent
  ↓
Company Report
  ↓
Financials + Valuation + Dividend + Ownership
  ↓
Structured JSON
```

------------------------------------------------------------------------

## Macro / Market Agent

Recommended:

``` text
daily transaction
IDX market summary
index daily
top changes
most traded
foreign flow
```

------------------------------------------------------------------------

## Sentiment / Catalyst Agent

Recommended:

``` text
news
filings
corporate actions
suspensions
foreign flow
broker activity
```

------------------------------------------------------------------------

## Screening Agent

Recommended:

``` text
companies
free float
industries
subindustries
subsectors
```

------------------------------------------------------------------------

# 39. API Tool Mapping untuk MCP / A2A

Jika API ini digunakan dalam MCP/A2A multi-agent system, sebaiknya
setiap endpoint dibungkus menjadi tool yang sempit.

Contoh:

``` json
{
  "name": "get_company_report",
  "description": "Get fundamental, valuation, dividend, ownership and peer data for an IDX-listed company.",
  "input": {
    "symbol": "string",
    "sections": "optional string"
  }
}
```

Contoh tool:

``` json
{
  "name": "get_daily_price",
  "description": "Get daily OHLCV and market capitalization for an IDX stock.",
  "input": {
    "symbol": "string",
    "start": "YYYY-MM-DD",
    "end": "YYYY-MM-DD"
  }
}
```

Contoh news tool:

``` json
{
  "name": "search_idx_news",
  "description": "Search IDX news articles by ticker, keyword, tag and date range.",
  "input": {
    "symbols": "optional string",
    "keyword": "optional string",
    "start": "optional YYYY-MM-DD",
    "end": "optional YYYY-MM-DD",
    "limit": "optional integer"
  }
}
```

------------------------------------------------------------------------

# 40. API Credit Optimization

API credit perlu diperhatikan ketika membuat AI Agent.

## Company Report

Default:

``` text
8 sections = 8 credits
```

Jika agent hanya membutuhkan valuation:

``` text
sections=valuation
```

maka tidak perlu meminta seluruh report.

### Jangan lakukan

``` text
User asks:
"Berapa PE BBCA?"

Agent:
Company Report seluruh section
```

### Lebih baik

``` text
User asks:
"Berapa PE BBCA?"

Agent:
Company Report
sections=valuation
```

------------------------------------------------------------------------

# 41. Date Range Optimization

Daily transaction maksimal 90 hari.

Jangan meminta:

``` text
start=2020-01-01
end=2026-10-01
```

Gunakan:

``` text
90-day chunks
```

jika memang membutuhkan historical data yang lebih panjang dan endpoint
mengizinkannya.

------------------------------------------------------------------------

# 42. Error Handling

HTTP status yang umum:

  Status   Arti
  -------- ---------------------------------
  `200`    Request berhasil
  `400`    Parameter/request invalid
  `404`    Resource/symbol tidak ditemukan
  `429`    Rate limit/API limit exceeded

Contoh:

``` json
{
  "error": "RATE_LIMIT_EXCEEDED",
  "message": "Rate limit exceeded. Consider upgrading."
}
```

Python:

``` python
response = requests.get(
    url,
    headers={"Authorization": api_key}
)

if response.status_code == 429:
    print("API rate limit exceeded")

response.raise_for_status()
```

------------------------------------------------------------------------

# 43. Security

Gunakan:

``` env
SECTORS_API_KEY=...
```

dan:

``` python
import os

api_key = os.getenv("SECTORS_API_KEY")
```

Jangan:

``` python
api_key = "sk-xxxxxxxx"
```

di source code.

Untuk architecture:

``` text
Frontend
   ↓
Backend / API Gateway
   ↓
Sectors API
```

Bukan:

``` text
Frontend
   ↓
Sectors API
```

karena API key tidak boleh diekspos ke browser.

------------------------------------------------------------------------

# 44. Minimal Python Client

``` python
import os
import requests

BASE_URL = "https://api.sectors.app/v2"
API_KEY = os.getenv("SECTORS_API_KEY")

HEADERS = {
    "Authorization": API_KEY
}

def get_company_report(symbol, sections=None):
    url = f"{BASE_URL}/company/report/{symbol}/"

    params = {}

    if sections:
        params["sections"] = ",".join(sections)

    response = requests.get(
        url,
        headers=HEADERS,
        params=params,
        timeout=30
    )

    response.raise_for_status()

    return response.json()


if __name__ == "__main__":
    data = get_company_report(
        "BBCA",
        ["overview", "valuation", "financials"]
    )

    print(data)
```

------------------------------------------------------------------------

# 45. Minimal CLI Test

Test API:

``` bash
export SECTORS_API_KEY="your_api_key"

curl \
  -H "Authorization: ${SECTORS_API_KEY}" \
  "https://api.sectors.app/v2/company/report/BBCA/?sections=valuation"
```

Test daily price:

``` bash
curl \
  -H "Authorization: ${SECTORS_API_KEY}" \
  "https://api.sectors.app/v2/daily/BBCA/?start=2026-09-01&end=2026-09-30"
```

Test news:

``` bash
curl \
  -H "Authorization: ${SECTORS_API_KEY}" \
  "https://api.sectors.app/v2/news/?symbols=BBCA&limit=10"
```

------------------------------------------------------------------------

# 46. Endpoint Quick Reference

  -------------------------------------------------------------------------------
  Endpoint                                    Main purpose
  ------------------------------------------- -----------------------------------
  `/v2/companies/`                            Company screener

  `/v2/company/report/{symbol}/`              Company report

  `/v2/company/quarterly/{symbol}/`           Quarterly financials

  `/v2/company/quarterly-dates/{symbol}/`     Available quarterly dates

  `/v2/company/segments/{symbol}/`            Revenue/cost segments

  `/v2/company/corporate-actions/{symbol}/`   Company corporate actions

  `/v2/company/shareholders/{symbol}/`        Shareholder composition

  `/v2/daily/{symbol}/`                       Daily OHLCV

  `/v2/close/`                                Full IDX daily close

  `/v2/idx-total/`                            Total IDX market cap

  `/v2/index-daily/{index}/`                  Index history

  `/v2/index-daily-universe/`                 Full index close

  `/v2/top-changes/`                          Top gainers/losers

  `/v2/most-traded/`                          Most traded stocks

  `/v2/ipo/{symbol}/`                         IPO performance

  `/v2/news/`                                 IDX news

  `/v2/filings/`                              Company filings

  `/v2/suspensions/`                          Stock suspensions

  `/v2/corporate-actions/`                    Corporate action calendar

  `/v2/foreign-flow/{symbol}/`                Foreign flow per stock

  `/v2/foreign-flow/`                         Full-universe foreign flow

  `/v2/broker-summary/{symbol}/`              Broker activity per stock

  `/v2/broker-summary-top/{symbol}/`          Top buyers/sellers

  `/v2/broker-activity/{broker_code}/`        Activity by broker

  `/v2/broker-activity-top/{broker_code}/`    Broker accumulation/distribution

  `/v2/broker-registry/`                      Broker registry

  `/v2/brokers/top/`                          Daily broker ranking

  `/v2/free-float/`                           Free float

  `/v2/industries/`                           Industry taxonomy

  `/v2/subindustries/`                        Sub-industry taxonomy

  `/v2/subsectors/`                           Sector/subsector taxonomy

  `/v2/tags/`                                 News/filing tags
  -------------------------------------------------------------------------------

------------------------------------------------------------------------

# 47. Official Documentation

The complete and authoritative reference is:

https://docs.sectors.app/

IDX API v2 documentation:

https://docs.sectors.app/api-references/v2/

Documentation index:

https://docs.sectors.app/llms.txt

------------------------------------------------------------------------

## Important Note

This document is a **developer-oriented condensed reference**, not a
replacement for the official Sectors documentation.

Endpoint schemas, available fields, pricing/credits, limits, and
response structures may change. Before production deployment, verify the
specific endpoint against the official documentation.
