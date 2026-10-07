#!/usr/bin/env python3
"""神奈川県公式CSV: A列=週、C列=横浜市の定点当たり報告数。"""
import csv
import io
import json
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

URL = "https://www.pref.kanagawa.jp/sys/eiken/003_center/0001_weekly/csv/20261001-influenza_2026.csv"
OUT = Path(__file__).resolve().parents[1] / "data" / "status.json"
JST = timezone(timedelta(hours=9))
YEAR = 2026


def fetch():
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "Mozilla/5.0 YokohamaFluSignage/2.0", "Accept": "text/csv,*/*"})
            with urllib.request.urlopen(req, timeout=30) as response:
                final = urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "www.pref.kanagawa.jp":
                    raise ValueError("予期しない転送先")
                raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise ValueError("CSVサイズ超過")
            return raw
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"CSV取得失敗: {last}")


def parse(raw, today=None):
    if not raw or raw.lstrip().startswith(b"<") or b"Request blocked by sandbox policy" in raw:
        raise ValueError("CSV以外の応答")
    for encoding in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV文字コード不明")
    rows = list(csv.reader(io.StringIO(text)))
    if not rows or [c.strip().lstrip("\ufeff") for c in rows[0][:3]] != ["週", "全県", "横浜市"]:
        raise ValueError("CSV見出し不一致")
    today = today or datetime.now(JST).date()
    found = {}
    for row in rows[1:]:
        if len(row) < 3:
            continue
        w, v = row[0].strip(), row[2].strip()
        if not re.fullmatch(r"(?:第)?(?:[1-9]|[1-4][0-9]|5[0-3])(?:週|[wW])?", w):
            continue
        week = int(re.search(r"\d+", w).group())
        try:
            end = date.fromisocalendar(YEAR, week, 7)
        except ValueError:
            continue
        if end > today or not v or v in ("-", "…", "...", "－"):
            continue
        if not re.fullmatch(r"\d+(?:\.\d+)?", v):
            raise ValueError(f"第{week}週の横浜市値が不正: {v!r}")
        value = float(v)
        if value > 10000 or week in found:
            raise ValueError("値の範囲外または週が重複")
        found[week] = value
    if not found:
        raise ValueError("公表済み横浜市値なし")
    week = max(found)
    if (today - date.fromisocalendar(YEAR, week, 7)).days > 21:
        raise ValueError("対象週が古い")
    # 先週比は必ず同じCSV内の直前週から計算。欠測なら差は表示しない。
    previous = found.get(week - 1)
    return {"region": "横浜市", "year": YEAR, "week": week,
            "perSentinel": found[week], "previousPerSentinel": previous,
            "difference": round(found[week] - previous, 2) if previous is not None else None,
            "metric": "定点当たり報告数", "sourceUrl": URL}


def main():
    payload = parse(fetch())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    if all(old.get(k) == v for k, v in payload.items()):
        print("変更なし")
        return
    payload["updatedAt"] = datetime.now(JST).isoformat(timespec="seconds")
    tmp = OUT.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))
        tmp.replace(OUT)
    finally:
        tmp.unlink(missing_ok=True)
    print("更新:", payload["week"], payload["perSentinel"], "先週差", payload["difference"])


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("更新失敗、既存JSONを維持:", repr(exc), file=sys.stderr)
        sys.exit(1)
