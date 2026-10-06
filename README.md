横浜市インフルエンザサイネージ（candidate）
4:3横向きの表示枠を全面使用。現場名は表示しません。
出典: https://www.pref.kanagawa.jp/sys/eiken/003_center/0001_weekly/csv/20261001-influenza_2026.csv
A列=週、B列=全県、C列=横浜市。C列の小数は定点当たり報告数であり感染者総数ではありません。
ZIPを展開し同じ階層へアップロード。既にdata/status.jsonに実データがある場合はバックアップしてから初期プレースホルダーを上書きしてください。assets/の3枚も同梱しています。既存画像を優先する場合はassets/を上書きしないでください。
.github/workflows/update.yml が Actions の手動実行・定期更新を行います。成功後 data/status.json の対象週と値を確認してください。
既存の js/config.js と data/content.json は新画面では参照しません。knowledge、tests、version.json は削除せず必要に応じて保管してください。
注意: 公式CSV本文・最新週の実値・実機表示は未確認です。初期JSONは未取得で、架空の数値を表示しません。警報/注意報の公式発令状況はこのCSVだけから判定しません。
