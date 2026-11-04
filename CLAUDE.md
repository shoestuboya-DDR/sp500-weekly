# CLAUDE.md

S&P500 投信（eMAXIS Slim 米国株式(S&P500)）の週末価格チェッカー。
仕様は [設計書.md](設計書.md)、セットアップは [README.md](README.md) を参照。

## 絶対に守ること

- このリポジトリは **公開リポジトリ**。メールアドレス・パスワード・トークンを
  コード、config.json、ドキュメント、コミットメッセージのどこにも書かない。
  通知まわりの値は GitHub Secrets（`GMAIL_USER` / `GMAIL_APP_PASSWORD` / `MAIL_TO`）だけで管理する
- コミット作成者はローカルの git config（GitHub の noreply アドレス）を使う。会社のアドレスでコミットしない
- push 先は `shoestuboya-DDR/sp500-weekly`。push 前に `gh auth status` で
  active account が `shoestuboya-DDR` になっているか確認する（`masuda-ddr` もログイン済みのため）
- 本物のメールを送る操作（Secrets を設定した状態での `src/update.py` 実行など）はローカルでやらない。
  ローカル確認は必ず `--dry-run` を付ける

## よく使うコマンド

```sh
# テスト（外部ライブラリ不要）
python -m unittest discover -s tests -t .

# 本番データでメールを送らずに動作確認（通知履歴も更新しない）
python src/update.py --dry-run

# 日付・データを差し替えて確認
python src/update.py --dry-run --today 2026-10-31 --csv-file path/to/data.csv

# 画面の確認
python -m http.server 8000 -d site
```

`--dry-run` でも `site/data/data.json` は上書きされる。
確認後は `git checkout site/data/data.json` で戻してからコミットする
（data.json と state/notified.json は Actions が毎日コミットするので、手元の変更とぶつかりやすい）。

## 実装上の約束

- Python は標準ライブラリだけで書く（Actions で `pip install` しない）
- 日本時間は `timezone(timedelta(hours=9))` の固定オフセットを使う。
  Windows には tz データベースがないので `zoneinfo` は使わない
- 騰落率の閾値判定は `Fraction` で行う。浮動小数だと −5.00% ちょうどの判定がぶれる
- 閾値（−5% / −4%）はコードに直書きせず、config.json の値から表示文字列も組み立てる
- `weekly.py` と、`notify.py` の判定・組み立て部分は I/O を持たない純粋関数に保つ
- 投信協会の CSV は HTTP ヘッダーが utf-8 でも中身は CP932。デコードは `fetch.decode_csv` を通す
- 仕様を変えたら 設計書.md と README.md も同じコミットで更新する

## 作業の流れ

1. 変更前に `git pull`（Actions のデータ更新コミットを取り込む）
2. 変更 → テスト → `--dry-run` で確認
3. コミットして push。push すると Actions が走るので、`gh run list` で成功を確認する

## Markdown

markdownlint を使っている。見出し・リストの前後は空行、1行120文字以内（表・コードブロック・見出しは除く）、
太字を見出し代わりに使わない。
