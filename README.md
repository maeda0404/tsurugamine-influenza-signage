# 神奈川県 インフルエンザ流行状況サイネージ

3:4縦型のGitHub Pages向け静的Webサイネージです。画面内に現場名、工事名、JV名、担当者名は表示しません。

## 公開方法
1. ZIPを展開し、展開後の中身をGitHubリポジトリ直下へ登録します。
2. GitHub Pagesを `main` ブランチの `/ (root)` から公開します。
3. `data/content.json` を実データで更新します。

## 画像
- `assets/handwash.png`
- `assets/healthcheck.png`
- `assets/ventilation.png`

## データ状態
神奈川県の公開データ取得処理は未接続です。架空数値を表示しないため、初期状態は「確認中」です。

## 主要設定
`js/config.js` でJSONパスと再読込間隔を変更できます。

## 注意
実機での3:4表示、ブラウザーのキオスク表示、長時間運転は未確認です。`tests/test-checklist.md` に沿って確認してください。
