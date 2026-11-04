# S&P500 週末チェック

eMAXIS Slim 米国株式(S&P500) の週末の基準価額と前週比を Web で確認し、
毎週メールで通知するツール。前週比が −5% 以下の週はアラート（赤）、
−4% 以下の週は注意（黄）として強調する。

- サイト: <https://shoestuboya-ddr.github.io/sp500-weekly/>

設計の詳細は [設計書.md](設計書.md) を参照。

## しくみ

- GitHub Actions が毎日 09:17 JST に `src/update.py` を実行する
- 投資信託協会の CSV から基準価額を取得し、`site/data/data.json` を更新してコミットする
- `site/` を GitHub Pages に公開する
- 週が確定したタイミング（通常は土曜朝）で、Gmail から1回だけメールを送る

## 初回セットアップ

### 1. Gmail（送信元アカウント）

1. Google アカウントの2段階認証プロセスを有効にする
2. 「アプリパスワード」を発行する（16桁）

### 2. GitHub Secrets

リポジトリの Settings → Secrets and variables → Actions に登録する。

| Secret 名 | 内容 |
| --- | --- |
| `GMAIL_USER` | 送信元の Gmail アドレス |
| `GMAIL_APP_PASSWORD` | 発行したアプリパスワード |
| `MAIL_TO` | 宛先。カンマ区切りで複数指定できる |

メールアドレスはリポジトリ内のファイルには書かないこと（公開リポジトリのため）。

### 3. GitHub Pages

Settings → Pages → Build and deployment の Source を「GitHub Actions」にする。

### 4. 初回実行

Actions タブ → update → Run workflow で手動実行する。
初回は直近の確定週のメールが1通届くので、それで送信テストを兼ねる。

公開 URL が決まったら `config.json` の `site_url` に設定すると、メール本文にリンクが入る。

## ローカルでの確認

Python 3.10 以上。外部ライブラリは不要。

```sh
# テスト
python -m unittest discover -s tests -t .

# メールを送らずに表示だけ（通知履歴も更新しない）
python src/update.py --dry-run

# 日付やデータを差し替えて動作確認
python src/update.py --dry-run --today 2026-10-31 --csv-file path/to/data.csv

# 画面の確認
python -m http.server 8000 -d site
```

## 設定（config.json）

| キー | 内容 |
| --- | --- |
| `alert_threshold_pct` | アラートの閾値（%）。既定は −5.0 |
| `caution_threshold_pct` | 注意の閾値（%）。既定は −4.0。`null` にすると注意判定をしない |
| `display_weeks` | 画面に表示する週数。既定は 52 |
| `stale_days` | 最新データがこの日数以上古いとエラー扱い。既定は 10 |
| `notify.weekly_summary` | `false` にするとアラート週・注意週だけ通知する |
| `notify.on_error` | 取得失敗時にエラーメールを送るか |
| `site_url` | メール本文に載せるサイトの URL |
