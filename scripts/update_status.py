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


# ============================================================
# 設定
# ============================================================

# 神奈川県 感染症発生動向調査 CSV
BASE = "https://www.pref.kanagawa.jp/sys/eiken/003_center/0001_weekly/csv"

# 出力先
OUT = Path("data/status.json")

# 過去45日分の日付をさかのぼって最新CSVを探す
SEARCH_DAYS = 45

# 新旧ファイル名に対応
DISEASES = {
    "influenza": {
        "labels": [
            "influenza",
        ],
        "display": "インフルエンザ",
    },
    "covid19": {
        "labels": [
            # 現在確認できている形式
            # 例: 20261119-covid19_2026.csv
            "covid19",

            # 過去・別表記にも対応
            "COVID-19",
            "covid-19",
            "covid_19",
        ],
        "display": "新型コロナ",
    },
}

JST = timezone(timedelta(hours=9))


# ============================================================
# CSV取得
# ============================================================

def fetch(url: str) -> bytes:
    """CSVを取得する"""

    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "tsurugamine-signage/2.2",
        },
    )

    with urllib.request.urlopen(req, timeout=15) as r:

        if r.status != 200:
            raise RuntimeError(f"HTTP {r.status}")

        # 異常に大きなレスポンスを防止
        body = r.read(2_000_001)

        if not body or len(body) > 2_000_000:
            raise RuntimeError("invalid response size")

        return body


# ============================================================
# 文字コード判定
# ============================================================

def decode_csv(body: bytes) -> str:
    """CSVの文字コードを判定してデコードする"""

    for enc in (
        "utf-8-sig",
        "cp932",
        "shift_jis",
    ):
        try:
            return body.decode(enc)
        except UnicodeDecodeError:
            pass

    raise RuntimeError("unsupported CSV encoding")


# ============================================================
# 横浜市データ解析
# ============================================================

def parse_yokohama(text: str) -> list[tuple[int, float]]:
    """CSVから横浜市の週別定点当たり報告数を取得する"""

    rows = list(
        csv.reader(
            io.StringIO(text)
        )
    )

    if not rows:
        raise RuntimeError("empty CSV")

    # 空白などによる列名の差異を吸収
    header = [
        re.sub(r"\s+", "", x)
        for x in rows[0]
    ]

    try:
        week_i = header.index("週")
        yokohama_i = header.index("横浜市")

    except ValueError as e:
        raise RuntimeError(
            "required columns not found"
        ) from e

    values: list[tuple[int, float]] = []

    for row in rows[1:]:

        if len(row) <= max(
            week_i,
            yokohama_i,
        ):
            continue

        w = row[week_i].strip()
        v = row[yokohama_i].strip()

        # 「週」が数字か確認
        if not re.fullmatch(
            r"\d{1,2}",
            w,
        ):
            continue

        # 横浜市の値が数字か確認
        if not re.fullmatch(
            r"\d+(?:\.\d+)?",
            v,
        ):
            continue

        values.append(
            (
                int(w),
                float(v),
            )
        )

    if not values:
        raise RuntimeError(
            "no Yokohama values"
        )

    # 週番号順
    values.sort(
        key=lambda x: x[0]
    )

    return values


# ============================================================
# URL候補生成
# ============================================================

def candidate_urls(
    day: datetime,
    disease: str,
) -> list[str]:
    """
    神奈川県CSVの新旧URL候補を作る。

    対応例:

    20261119_influenza.csv
    20261119_influenza_2026.csv
    20261119-influenza_2026.csv
    20261119_influenza-2026.csv

    COVID-19:

    20261119-covid19_2026.csv
    20261119_COVID-19.csv
    20261119_COVID-19_2026.csv
    20261119-covid-19_2026.csv
    20261119_covid_19_2026.csv

    など。
    """

    stamp = day.strftime("%Y%m%d")
    year = day.strftime("%Y")

    labels = DISEASES[disease]["labels"]

    urls: list[str] = []

    for label in labels:

        # ----------------------------------------------------
        # 1. 日付_病名.csv
        #
        # 例:
        # 20261119_influenza.csv
        # 20261119_covid19.csv
        # ----------------------------------------------------

        urls.append(
            f"{BASE}/{stamp}_{label}.csv"
        )

        # ----------------------------------------------------
        # 2. 日付_病名_年.csv
        #
        # 例:
        # 20261119_influenza_2026.csv
        # 20261119_covid19_2026.csv
        # ----------------------------------------------------

        urls.append(
            f"{BASE}/{stamp}_{label}_{year}.csv"
        )

        # ----------------------------------------------------
        # 3. 日付-病名_年.csv
        #
        # 現在のCOVID-19で確認できている形式:
        #
        # 20261119-covid19_2026.csv
        # ----------------------------------------------------

        urls.append(
            f"{BASE}/{stamp}-{label}_{year}.csv"
        )

        # ----------------------------------------------------
        # 4. 日付_病名-年.csv
        #
        # 念のため旧形式・表記揺れにも対応
        # ----------------------------------------------------

        urls.append(
            f"{BASE}/{stamp}_{label}-{year}.csv"
        )

        # ----------------------------------------------------
        # 5. 日付-病名.csv
        #
        # 年なし + ハイフン形式にも対応
        # ----------------------------------------------------

        urls.append(
            f"{BASE}/{stamp}-{label}.csv"
        )

    # 重複URLを順番を維持したまま削除
    return list(
        dict.fromkeys(urls)
    )


# ============================================================
# 最新CSV検索
# ============================================================

def find_latest(
    disease: str,
    now: datetime,
) -> dict:
    """
    最新の有効なCSVを探して
    横浜市の最新値・前週値を返す。
    """

    errors: list[str] = []

    for ago in range(
        SEARCH_DAYS + 1
    ):

        day = now - timedelta(
            days=ago
        )

        for url in candidate_urls(
            day,
            disease,
        ):

            try:

                body = fetch(url)

                text = decode_csv(body)

                values = parse_yokohama(
                    text
                )

                # 最新週
                week, current = values[-1]

                # 前週
                if len(values) > 1:

                    prev_week, previous = (
                        values[-2]
                    )

                else:

                    prev_week = None
                    previous = None

                # GitHub Actionsのログで
                # 採用URLを確認できるようにする
                print(
                    f"FOUND {disease}: "
                    f"{url} "
                    f"(week={week}, "
                    f"value={current})"
                )

                return {
                    "label":
                        DISEASES[disease][
                            "display"
                           ],

                    "week":
                        week,

                    "value":
                        current,

                    "previousWeek":
                        prev_week,

                    "previousValue":
                        previous,

                 
                        round(
                            current - previous,
                            2,
                        )
                        if previous is not None
                        else None
                    ),

                    "sourceUrl":
                        url,

                    "publishedDate":
                        day.strftime(
                            "%Y-%m-%d"
                        ),
                }

            except Exception as e:

                errors.append(
                    f"{url}: "
                    f"{type(e).__name__}"
                )

    raise RuntimeError(
        f"no valid {disease} CSV found; "
        f"checked {len(errors)} candidates"
    )


# ============================================================
# JSON安全書き込み
# ============================================================

def atomic_write(
    path: Path,
    data: dict,
) -> None:
    """
    status.jsonを一時ファイル経由で
    安全に上書きする。
    """

    path.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    fd, tmp = tempfile.mkstemp(
        prefix=path.name + ".",
        dir=path.parent,
    )

    try:

        with os.fdopen(
            fd,
            "w",
            encoding="utf-8",
        ) as f:

            json.dump(
                data,
                f,
                ensure_ascii=False,
                indent=2,
            )

            f.write("\n")

            f.flush()

            os.fsync(
                f.fileno()
            )

        os.replace(
            tmp,
            path,
        )

    finally:

        if os.path.exists(tmp):
            os.unlink(tmp)


# ============================================================
# メイン処理
# ============================================================

def main() -> int:

    now = datetime.now(JST)

    # 更新失敗時に現在のstatus.jsonを残す
    old = {}

    if OUT.exists():

        try:

            old = json.loads(
                OUT.read_text(
                    encoding="utf-8"
                )
            )

        except Exception:

            old = {}

    try:

        # ------------------------------
        # インフルエンザ
        # ------------------------------

        flu = find_latest(
            "influenza",
            now,
        )

        # ------------------------------
        # 新型コロナ
        # ------------------------------

        covid = find_latest(
            "covid19",
            now,
        )

        # ------------------------------
        # 出力JSON
        # ------------------------------

        result = {
            "schemaVersion": 2,

            "area":
                "横浜市",

            "unit":
                "定点当たり報告数",

            "updatedAt":
                now.isoformat(
                    timespec="seconds"
                ),

            # 新形式
            "influenza":
                flu,

            "covid19":
                covid,

            # 既存HTML / JSとの互換性維持
            # 従来フィールドは
            # インフルエンザの値を入れる
            "week":
                flu["week"],

            "value":
                flu["value"],

            "previousValue":
                flu["previousValue"],

            "change":
                flu["change"],

            "sourceUrl":
                flu["sourceUrl"],
        }

        # ------------------------------
        # 書き込み
        # ------------------------------

        atomic_write(
            OUT,
            result,
        )

        # Actionsログ表示
        print(
            json.dumps(
                result,
                ensure_ascii=False,
                indent=2,
            )
        )

        return 0

    except Exception as e:

        print(
            f"ERROR: {e}",
            file=sys.stderr,
        )

        # 既存データは削除しない
        if old:

            print(
                "Existing data/status.json "
                "preserved.",
                file=sys.stderr,
            )

        return 1


if __name__ == "__main__":
    raise SystemExit(
        main()
    )
