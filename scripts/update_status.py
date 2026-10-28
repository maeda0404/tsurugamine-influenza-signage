#!/usr/bin/env python3
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import tempfile
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

BASE = "https://www.pref.kanagawa.jp/sys/eiken/003_center/0001_weekly/csv"
OUT = Path("data/status.json")
SEARCH_DAYS = 45
DISEASES = {
    "influenza": {"labels": ["influenza"], "display": "インフルエンザ"},
    "covid19": {"labels": ["covid-19", "covid_19"], "display": "新型コロナ"},
}
JST = timezone(timedelta(hours=9))


def fetch(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "tsurugamine-signage/2.0"})
    with urllib.request.urlopen(req, timeout=15) as r:
        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")
        body = r.read(2_000_001)
        if not body or len(body) > 2_000_000:
            raise RuntimeError("invalid response size")
        return body


def decode_csv(body: bytes) -> str:
    for enc in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            pass
    raise RuntimeError("unsupported CSV encoding")


def parse_yokohama(text: str) -> list[tuple[int, float]]:
    rows = list(csv.reader(io.StringIO(text)))
    if not rows:
        raise RuntimeError("empty CSV")
    header = [re.sub(r"\s+", "", x) for x in rows[0]]
    try:
        week_i = header.index("週")
        yokohama_i = header.index("横浜市")
    except ValueError as e:
        raise RuntimeError("required columns not found") from e
    values: list[tuple[int, float]] = []
    for row in rows[1:]:
        if len(row) <= max(week_i, yokohama_i):
            continue
        w = row[week_i].strip()
        v = row[yokohama_i].strip()
        if re.fullmatch(r"\d{1,2}", w) and re.fullmatch(r"\d+(?:\.\d+)?", v):
            values.append((int(w), float(v)))
    if not values:
        raise RuntimeError("no Yokohama values")
    values.sort(key=lambda x: x[0])
    return values


def candidate_urls(day: datetime, disease: str) -> list[str]:
    stamp = day.strftime("%Y%m%d")
    year = day.strftime("%Y")
    labels = DISEASES[disease]["labels"]
    urls = []
    for label in labels:
        urls.append(f"{BASE}/{stamp}-{label}_{year}.csv")
        urls.append(f"{BASE}/{stamp}_{label}_{year}.csv")
    return urls


def find_latest(disease: str, now: datetime) -> dict:
    errors = []
    for ago in range(SEARCH_DAYS + 1):
        day = now - timedelta(days=ago)
        for url in candidate_urls(day, disease):
            try:
                values = parse_yokohama(decode_csv(fetch(url)))
                week, current = values[-1]
                prev_week, previous = values[-2] if len(values) > 1 else (None, None)
                return {
                    "label": DISEASES[disease]["display"],
                    "week": week,
                    "value": current,
                    "previousWeek": prev_week,
                    "previousValue": previous,
                    "change": round(current - previous, 2) if previous is not None else None,
                    "sourceUrl": url,
                    "publishedDate": day.strftime("%Y-%m-%d"),
                }
            except Exception as e:
                errors.append(f"{url}: {type(e).__name__}")
    raise RuntimeError(f"no valid {disease} CSV found; checked {len(errors)} candidates")


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=path.name + ".", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def main() -> int:
    now = datetime.now(JST)
    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except Exception:
            old = {}
    try:
        flu = find_latest("influenza", now)
        covid = find_latest("covid19", now)
        result = {
            "schemaVersion": 2,
            "area": "横浜市",
            "unit": "定点当たり報告数",
            "updatedAt": now.isoformat(timespec="seconds"),
            "influenza": flu,
            "covid19": covid,
            # Existing display compatibility
            "week": flu["week"],
            "value": flu["value"],
            "previousValue": flu["previousValue"],
            "change": flu["change"],
            "sourceUrl": flu["sourceUrl"],
        }
        atomic_write(OUT, result)
        print(json.dumps(result, ensure_ascii=False))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        if old:
            print("Existing data/status.json preserved.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
