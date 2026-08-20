#!/usr/bin/env python3
"""
fetch_idx.py — Ambil data kuotasi saham IDX dari Yahoo Finance (endpoint publik,
tanpa API key) dan simpan sebagai JSON.

CARA PAKAI:
    python fetch_idx.py APLN ISAT CTRA DMAS

CATATAN JUJUR SOAL DATA:
- Yahoo Finance sendiri melabel data bursa non-US (termasuk IDX) sebagai
  "Delayed Quote" — biasanya delay ~15-20 menit, BUKAN tick-by-tick real-time.
- Tapi ini jauh lebih fresh dibanding snapshot dari Google/Bing search yang
  bisa basi berminggu-minggu.
- Endpoint ini tidak resmi/tidak didokumentasikan Yahoo — bisa berubah atau
  di-rate-limit sewaktu-waktu tanpa pemberitahuan. Jangan pakai untuk sistem
  produksi/trading otomatis tanpa fallback.

CARA OTOMATISASI (biar Claude bisa baca tanpa lu feed manual tiap kali):
1. Push script ini ke repo GitHub (bisa public atau private).
2. Bikin GitHub Actions workflow yang jalanin script ini tiap N menit selama
   jam bursa (misal cron "*/15 9-16 * * 1-5" waktu WIB, sesuaikan ke UTC),
   lalu commit hasil idx_data.json balik ke repo.
3. Kasih tau Claude link raw file-nya, misal:
   https://raw.githubusercontent.com/<user>/<repo>/main/idx_data.json
   Claude BISA fetch URL raw.githubusercontent.com (domain itu di-allow),
   jadi setiap ngobrol tinggal kasih link itu, Claude tarik data terbarunya.
"""

import sys
import json
import time
import urllib.request
import urllib.error
from datetime import datetime, timezone


YAHOO_CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{ticker}.JK"
HEADERS = {
    # Yahoo suka nolak request tanpa User-Agent yang wajar
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    )
}


def fetch_one(ticker: str) -> dict:
    """Ambil kuotasi satu saham IDX. ticker tanpa suffix, misal 'APLN'."""
    url = YAHOO_CHART_URL.format(ticker=ticker.upper())
    req = urllib.request.Request(url, headers=HEADERS)

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            raw = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        return {"ticker": ticker, "error": f"HTTP {e.code}"}
    except urllib.error.URLError as e:
        return {"ticker": ticker, "error": f"Gagal konek: {e.reason}"}
    except Exception as e:  # noqa: BLE001 — mau tetap jalan lanjut ke ticker berikutnya
        return {"ticker": ticker, "error": str(e)}

    try:
        result = raw["chart"]["result"][0]
        meta = result["meta"]
    except (KeyError, IndexError, TypeError):
        return {"ticker": ticker, "error": "Format respons tidak dikenali / ticker salah"}

    quote_time = meta.get("regularMarketTime")
    quote_time_iso = (
        datetime.fromtimestamp(quote_time, tz=timezone.utc).isoformat()
        if quote_time
        else None
    )

    return {
        "ticker": ticker.upper(),
        "price": meta.get("regularMarketPrice"),
        "prev_close": meta.get("previousClose") or meta.get("chartPreviousClose"),
        "day_high": meta.get("regularMarketDayHigh"),
        "day_low": meta.get("regularMarketDayLow"),
        "volume": meta.get("regularMarketVolume"),
        "currency": meta.get("currency"),
        "exchange": meta.get("exchangeName"),
        "quote_time_utc": quote_time_iso,
        "market_state": meta.get("marketState"),
        "note": "Delayed quote (~15-20 menit), bukan real-time tick-by-tick",
    }


def main(tickers: list[str]) -> None:
    if not tickers:
        print("Kasih minimal satu kode ticker, contoh: python fetch_idx.py APLN ISAT")
        sys.exit(1)

    out = {
        "fetched_at_utc": datetime.now(timezone.utc).isoformat(),
        "source": "Yahoo Finance (endpoint publik tidak resmi)",
        "data": [],
    }

    for t in tickers:
        row = fetch_one(t)
        out["data"].append(row)
        if "error" in row:
            print(f"[GAGAL] {t}: {row['error']}")
        else:
            print(
                f"[OK] {row['ticker']}: {row['price']} "
                f"(prev {row['prev_close']}, vol {row['volume']}) "
                f"@ {row['quote_time_utc']}"
            )
        time.sleep(0.5)  # sopan santun ke server, hindari rate-limit

    with open("idx_data.json", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)

    print("\nTersimpan ke idx_data.json")


if __name__ == "__main__":
    main(sys.argv[1:])
