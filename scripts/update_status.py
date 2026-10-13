#!/usr/bin/env python3
"""神奈川県公式の最新インフルエンザCSVを探索し、横浜市の最新値をJSONへ保存する。"""

import csv
import io
import json
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

BASE_URL = (
    "https://www.pref.kanagawa.jp/sys/eiken/003_center/0001_weekly/csv/"
)
OUT = Path(__file__).resolve().parents[1] / "data" / "status.json"
JST = timezone(timedelta(hours=9))
USER_AGENT = "Mozilla/5.0 YokohamaFluSignage/3.0"
MAX_BYTES = 5_000_000
SEARCH_DAYS = 45
MAX_DATA_AGE_DAYS = 21
MISSING_VALUES = {"", "-", "…", "...", "－"}


def candidate_urls(today):
    """新しい日付から順に、当年・前年の候補URLを重複なく返す。"""
    seen = set()
    for days_ago in range(SEARCH_DAYS + 1):
        published = today - timedelta(days=days_ago)
        for data_year in (published.year, published.year - 1):
            url = (
                f"{BASE_URL}{published:%Y%m%d}-influenza_{data_year}.csv"
            )
            if url not in seen:
                seen.add(url)
                yield url, data_year


def download(url):
    """候補CSVを取得する。存在しない候補はNoneを返す。"""
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/csv,*/*;q=0.8",
            "Cache-Control": "no-cache",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            final = urlsplit(response.geturl())
            if final.scheme != "https" or final.hostname != "www.pref.kanagawa.jp":
                raise ValueError("予期しない転送先")
            raw = response.read(MAX_BYTES + 1)
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404, 410):
            return None
        raise RuntimeError(f"HTTP {exc.code}: {url}") from exc

    if len(raw) > MAX_BYTES:
        raise ValueError("CSVサイズ超過")
    if not raw or raw.lstrip().startswith(b"<"):
        return None
    return raw


def decode_csv(raw):
    for encoding in ("utf-8-sig", "cp932"):
        try:
            return raw.decode(encoding)
        except UnicodeDecodeError:
            pass
    raise ValueError("CSV文字コード不明")


def parse_csv(raw, data_year, source_url, today):
    """CSVを検証し、最新の公表済み週をJSON用辞書にする。"""
    if b"Request blocked by sandbox policy" in raw:
        raise ValueError("CSV以外の応答")

    rows = list(csv.reader(io.StringIO(decode_csv(raw))))
    if not rows:
        raise ValueError("CSVが空です")

    header = [cell.strip().lstrip("\ufeff") for cell in rows[0]]
    try:
        week_col = header.index("週")
        yokohama_col = header.index("横浜市")
    except ValueError as exc:
        raise ValueError("CSV見出し不一致") from exc

    found = {}
    week_pattern = re.compile(r"(?:第)?([1-9]|[1-4][0-9]|5[0-3])(?:週|[wW])?")
    number_pattern = re.compile(r"\d+(?:\.\d+)?")

    for row in rows[1:]:
        if len(row) <= max(week_col, yokohama_col):
            continue

        week_text = row[week_col].strip()
        value_text = row[yokohama_col].strip()
        match = week_pattern.fullmatch(week_text)
        if not match or value_text in MISSING_VALUES:
            continue

        week = int(match.group(1))
        try:
            week_end = date.fromisocalendar(data_year, week, 7)
        except ValueError:
            continue

        if week_end > today:
            continue
        if not number_pattern.fullmatch(value_text):
            raise ValueError(f"第{week}週の横浜市値が不正: {value_text!r}")

        value = float(value_text)
        if value > 10000:
            raise ValueError(f"第{week}週の横浜市値が範囲外: {value}")
        if week in found:
            raise ValueError(f"第{week}週が重複")
        found[week] = value

    if not found:
        raise ValueError("公表済み横浜市値なし")

    week = max(found)
    week_end = date.fromisocalendar(data_year, week, 7)
    age_days = (today - week_end).days
    if age_days > MAX_DATA_AGE_DAYS:
        raise ValueError(f"対象週が古い: 第{week}週、{age_days}日前")

    previous = found.get(week - 1)
    return {
        "region": "横浜市",
        "year": data_year,
        "week": week,
        "perSentinel": found[week],
        "previousPerSentinel": previous,
        "difference": round(found[week] - previous, 2) if previous is not None else None,
        "metric": "定点当たり報告数",
        "sourceUrl": source_url,
    }


def fetch_latest(today):
    """最新日付の有効な公式CSVを探す。"""
    errors = []
    for url, data_year in candidate_urls(today):
        for attempt in range(3):
            try:
                raw = download(url)
                if raw is None:
                    break
                payload = parse_csv(raw, data_year, url, today)
                print("採用CSV:", url)
                return payload
            except (urllib.error.URLError, TimeoutError) as exc:
                if attempt < 2:
                    time.sleep(2 * (attempt + 1))
                    continue
                errors.append(f"{url}: 通信失敗 {exc}")
            except ValueError as exc:
                errors.append(f"{url}: {exc}")
                break
            except RuntimeError as exc:
                errors.append(str(exc))
                break

    detail = errors[-3:] if errors else ["候補CSVが見つかりませんでした"]
    raise RuntimeError("最新CSV取得失敗: " + " / ".join(detail))


def load_old():
    try:
        value = json.loads(OUT.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def write_json(payload):
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    try:
        tmp.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        check = json.loads(tmp.read_text(encoding="utf-8"))
        if not isinstance(check, dict):
            raise ValueError("生成JSONがオブジェクトではありません")
        tmp.replace(OUT)
    finally:
        tmp.unlink(missing_ok=True)


def main():
    now = datetime.now(JST)
    payload = fetch_latest(now.date())
    old = load_old()

    comparable_keys = tuple(payload.keys())
    if all(old.get(key) == payload[key] for key in comparable_keys):
        print(
            "変更なし:",
            f"{payload['year']}年第{payload['week']}週",
            payload["perSentinel"],
        )
        return

    payload["updatedAt"] = now.isoformat(timespec="seconds")
    write_json(payload)
    print(
        "更新:",
        f"{payload['year']}年第{payload['week']}週",
        payload["perSentinel"],
        "先週差",
        payload["difference"],
    )


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print("更新失敗、既存JSONを維持:", repr(exc), file=sys.stderr)
        sys.exit(1)
