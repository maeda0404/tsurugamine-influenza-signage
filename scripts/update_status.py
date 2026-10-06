#!/usr/bin/env python3
"""神奈川県2026年インフルエンザCSVの横浜市・定点当たり報告数を更新。"""
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
    last_error = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(URL, headers={
                "User-Agent": "Mozilla/5.0 (compatible; YokohamaFluSignage/1.1)",
                "Accept": "text/csv,*/*",
                "Cache-Control": "no-cache",
            })
            with urllib.request.urlopen(request, timeout=30) as response:
                final = urlsplit(response.geturl())
                if final.scheme != "https" or final.hostname != "www.pref.kanagawa.jp":
                    raise ValueError("想定外の転送先")
                raw = response.read(5_000_001)
            if len(raw) > 5_000_000:
                raise ValueError("CSVサイズ超過")
            return raw
        except Exception as error:
            last_error = error
            if attempt < 2:
                time.sleep(2 * (attempt + 1))
    raise RuntimeError(f"CSV取得失敗: {last_error}") from last_error


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
    if not rows or [cell.strip().lstrip("\ufeff") for cell in rows[0][:3]] != ["週", "全県", "横浜市"]:
        raise ValueError("見出し不一致: A=週 B=全県 C=横浜市")
    today = today or datetime.now(JST).date()
    candidates = []
    for row in rows[1:]:
        if len(row) < 3:
            continue
        week_text, value_text = row[0].strip(), row[2].strip()
        if not re.fullmatch(r"(?:第)?(?:[1-9]|[1-4][0-9]|5[0-3])(?:週|[wW])?", week_text):
            continue
        if not value_text or value_text in ("-", "…", "...", "－"):
            continue
        week = int(re.search(r"\d+", week_text).group())
        try:
            week_end = date.fromisocalendar(YEAR, week, 7)
        except ValueError:
            continue
        if week_end > today:
            continue
        if not re.fullmatch(r"\d+(?:\.\d+)?", value_text):
            raise ValueError(f"第{week}週の横浜市値が不正: {value_text!r}")
        value = float(value_text)
        if value > 10000:
            raise ValueError("値が範囲外")
        candidates.append((week, value))
    if not candidates:
        raise ValueError("公表済みの横浜市値なし")
    week = max(w for w, _ in candidates)
    values = [v for w, v in candidates if w == week]
    if len(values) != 1:
        raise ValueError("同一週の値が重複")
    if (today - date.fromisocalendar(YEAR, week, 7)).days > 21:
        raise ValueError("対象週が古い")
    return {
        "region": "横浜市", "year": YEAR, "week": week,
        "perSentinel": values[0], "metric": "定点当たり報告数", "sourceUrl": URL,
    }


def main():
    payload = parse(fetch())
    OUT.parent.mkdir(parents=True, exist_ok=True)
    try:
        old = json.loads(OUT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        old = {}
    if all(old.get(key) == value for key, value in payload.items()):
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
    print("更新:", payload["week"], payload["perSentinel"])


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print("更新失敗、既存JSONを維持:", repr(error), file=sys.stderr)
        sys.exit(1)
