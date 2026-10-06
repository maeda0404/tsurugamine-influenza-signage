#!/usr/bin/env python3
"""神奈川県の2026年インフルエンザCSVから週別報告人数を取得する。

CSVの実際の列構造はこの環境では未検証。--inspect で列・先頭行を確認し、
環境変数 KANAGAWA_WEEK_COLUMN, KANAGAWA_COUNT_COLUMN,
KANAGAWA_REGION_COLUMN を実際のCSVの見出しに合わせて設定する。
不明な列・地域・週は推測せず失敗し、既存JSONを上書きしない。
"""
import argparse
import csv
import io
import json
import os
import re
import sys
import time
import urllib.request
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

SOURCE_URL = "https://www.pref.kanagawa.jp/sys/eiken/003_center/0001_weekly/csv/20261001-influenza_2026.csv"
ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "status.json"
JST = timezone(timedelta(hours=9))
MAX_BYTES = 5_000_000


def download(url):
    parts = urlsplit(url)
    if parts.scheme != "https" or parts.hostname != "www.pref.kanagawa.jp" or parts.username or parts.password:
        raise ValueError("神奈川県の指定HTTPSホスト以外は取得しません")
    last = None
    for attempt in range(3):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "Kanagawa-Flu-Signage/1.0", "Accept": "text/csv,*/*"})
            with urllib.request.urlopen(request, timeout=25) as response:
                if response.geturl().split("/")[2] != "www.pref.kanagawa.jp":
                    raise ValueError("想定外のリダイレクト先")
                raw = response.read(MAX_BYTES + 1)
            if len(raw) > MAX_BYTES:
                raise ValueError("CSVサイズ超過")
            return raw
        except Exception as exc:
            last = exc
            if attempt < 2:
                time.sleep(attempt + 1)
    raise RuntimeError(f"CSV取得失敗: {last}") from last


def decode_csv(raw):
    for encoding in ("utf-8-sig", "cp932"):
        try:
            text = raw.decode(encoding)
            break
        except UnicodeDecodeError:
            continue
    else:
        raise ValueError("CSV文字コードを判定できません")
    if "\x00" in text or "Request blocked by sandbox policy" in text or "<html" in text.lower():
        raise ValueError("CSV以外の応答です")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",\t;")
        delimiter = dialect.delimiter
    except csv.Error:
        delimiter = ","
    rows = list(csv.reader(io.StringIO(text), delimiter=delimiter))
    if not rows or not any(len(row) > 1 for row in rows):
        raise ValueError("CSVに複数列がありません")
    return rows


def clean(value):
    return re.sub(r"[\s\u3000]+", "", str(value or "")).strip()


def header_index(header, configured, label):
    if not configured:
        raise ValueError(f"{label}の列名が未設定です。--inspectで確認してください")
    found = [i for i, name in enumerate(header) if clean(name) == clean(configured)]
    if len(found) != 1:
        raise ValueError(f"{label}の列が見つからないか重複しています: {configured!r}")
    return found[0]


def parse_week(text):
    value = clean(text)
    # 年と週を同じセルに明記した形式だけを受理する。
    match = re.fullmatch(r"(20\d{2})年?第?(\d{1,2})週", value)
    if not match:
        match = re.fullmatch(r"(20\d{2})[-/]W?(\d{1,2})", value, re.I)
    if not match:
        raise ValueError(f"対象年・週を特定できません: {text!r}")
    year, week = map(int, match.groups())
    date.fromisocalendar(year, week, 1)
    return year, week


def parse_count(text):
    value = clean(text).replace(",", "")
    if not re.fullmatch(r"\d+", value):
        raise ValueError(f"患者報告人数が非負整数ではありません: {text!r}")
    return int(value)


def extract(rows, week_column, count_column, region_column, header_row):
    if header_row < 1 or header_row > len(rows):
        raise ValueError("見出し行番号が範囲外です")
    header = rows[header_row - 1]
    wi = header_index(header, week_column, "対象週")
    ci = header_index(header, count_column, "週別患者報告人数")
    ri = header_index(header, region_column, "地域")
    if len({wi, ci, ri}) != 3:
        raise ValueError("対象週・人数・地域は異なる列を指定してください")
    # 定点当たりの率を実人数として誤掲示しない。
    if any(word in clean(header[ci]) for word in ("定点当たり", "定点あたり", "率", "平均")):
        raise ValueError("人数列に率・定点当たりの列が指定されています")
    matches = []
    for line, row in enumerate(rows[header_row:], header_row + 1):
        if len(row) <= max(wi, ci, ri) or clean(row[ri]) != "神奈川県":
            continue
        if not clean(row[ci]):
            continue
        year, week = parse_week(row[wi])
        if year != 2026:
            continue
        sunday = date.fromisocalendar(year, week, 7)
        if sunday > datetime.now(JST).date():
            continue
        matches.append((year, week, parse_count(row[ci]), line))
    if not matches:
        raise ValueError("2026年の神奈川県全体の公表済み週別報告人数がありません")
    latest_week = max((year, week) for year, week, _, _ in matches)
    latest = [item for item in matches if item[:2] == latest_week]
    if len(latest) != 1:
        raise ValueError(f"最新週の神奈川県行が複数あります: {latest_week}")
    return latest[0]


def inspect(rows, limit=8):
    for i, row in enumerate(rows[:limit], 1):
        print(f"{i}: " + json.dumps(row[:25], ensure_ascii=False))
    print("列名を確認後、KANAGAWA_*_COLUMNとKANAGAWA_HEADER_ROWを設定してください")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inspect", action="store_true", help="CSVの冒頭行を表示。JSONは更新しない")
    parser.add_argument("--csv-file", type=Path, help="ローカルCSVで検証。未指定時は県URLを取得")
    args = parser.parse_args(argv)
    rows = decode_csv(args.csv_file.read_bytes() if args.csv_file else download(SOURCE_URL))
    if args.inspect:
        inspect(rows)
        return 0
    year, week, count, line = extract(
        rows,
        os.getenv("KANAGAWA_WEEK_COLUMN", ""),
        os.getenv("KANAGAWA_COUNT_COLUMN", ""),
        os.getenv("KANAGAWA_REGION_COLUMN", ""),
        int(os.getenv("KANAGAWA_HEADER_ROW", "1")),
    )
    now = datetime.now(JST).isoformat(timespec="seconds")
    payload = {
        "region": "神奈川県",
        "week": f"{year}-W{week:02d}",
        "reportedCases": count,
        "metricLabel": "定点医療機関からの週別患者報告数",
        "sourceUrl": SOURCE_URL,
        "updatedAt": now,
        "sourceRow": line,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    tmp = OUT.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        json.loads(tmp.read_text(encoding="utf-8"))
        tmp.replace(OUT)
    finally:
        tmp.unlink(missing_ok=True)
    print(f"更新: {payload['week']} 神奈川県 定点医療機関の報告数 {count}人 -> {OUT}")
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print(f"更新中止（既存JSONは維持）: {exc}", file=sys.stderr)
        sys.exit(1)

