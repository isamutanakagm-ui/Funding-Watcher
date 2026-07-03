# セットアップ手順書 — GitHub 自動実行版

## この手順で得られるもの
- ✅ 毎朝 6:00 (JST) に自動で 8 機関の公募情報を収集
- ✅ 誰でも Web ブラウザで最新一覧を閲覧 (URL 共有で OK)
- ✅ 新規公募があれば本人のメールに自動通知
- ✅ ジョブ産雇・上司・人事・他対象者は **URL を渡すだけ** で全員閲覧可
- ✅ ローカルPCの電源ON不要、Python不要、コスト無料

---

## 前提
- GitHub アカウント（無料）— 未取得なら https://github.com/signup で 5 分で作成
- Gmail アカウント（メール通知が要る場合のみ）

---

## 手順 1: リポジトリ作成 (3分)

1. GitHub 右上の「+」→ **New repository**
2. Repository name: `funding-watcher`（任意）
3. **Public** を選択（Private だと Actions の無料枠が月2000分に制限。Public なら無制限）
4. 「Create repository」

## 手順 2: プロジェクト一式をアップロード (2分)

1. 配布 ZIP を解凍
2. GitHub の作ったリポジトリで「uploading an existing file」リンクをクリック
3. `funding_watcher/` の中身をすべてドラッグ&ドロップ
    - `watcher.py`, `send_mail.py`, `README.md`, `SETUP.md`
    - `.github/workflows/daily.yml`, `.github/workflows/pages.yml`
4. コミットメッセージ「initial commit」で「Commit changes」

## 手順 3: Actions 権限を有効化 (1分)

1. リポジトリの **Settings** タブ
2. 左メニュー **Actions → General**
3. 「Workflow permissions」で **Read and write permissions** にチェック → Save
    - これで daily.yml が差分DB をコミットできるようになる

## 手順 4: GitHub Pages を有効化 (1分)

1. **Settings → Pages**
2. Source: **GitHub Actions** を選択
    - `pages.yml` が自動で動く

## 手順 5: 初回実行 (2分)

1. **Actions** タブ → 左メニュー **Daily Funding Recruitment Watch**
2. 右上「Run workflow」ボタン → 「Run workflow」
3. 2-3 分で緑チェック ✅
4. **Actions** タブ → **Deploy to GitHub Pages** が続けて自動実行 → 緑チェック
5. **Settings → Pages** に表示された URL を開く
    - 例: `https://<あなたのユーザー名>.github.io/funding-watcher/`
6. ダッシュボードが表示されれば完了 🎉

## 手順 6: メール通知を有効化する場合 (任意, 5分)

### 6-1. Gmail のアプリパスワードを取得
Google アカウントは通常のパスワードでは SMTP ログインできないので、専用のアプリパスワードを作る。

1. https://myaccount.google.com/security にアクセス
2. **2段階認証プロセス**を有効化（未設定なら）
3. 検索窓で「アプリパスワード」→ 選択
4. アプリ名「funding-watcher」で作成 → 16 桁パスワードをコピー

### 6-2. GitHub Secrets に登録
1. リポジトリの **Settings → Secrets and variables → Actions**
2. 「New repository secret」で以下を **5つ** 登録:

| Name | Value 例 |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | あなたの Gmail アドレス |
| `SMTP_PASS` | 6-1 で取得した 16 桁アプリパスワード |
| `MAIL_TO`   | 通知先メール（自分でも良い） |

### 6-3. 動作確認
- Actions タブから **Run workflow** で手動実行
- 新規公募があれば自動でメールが届く
- 新規0件の日は送信スキップ（うるさくならない）

---

## 横展開のときにやること

**他の対象社員に見せる**:
- Pages の URL を Slack / Teams / メールで共有するだけ
- 見る側は GitHub アカウントすら不要

**別の人向けにフォークして使う**:
- リポジトリ右上「Fork」→ その人のアカウントに複製
- `watcher.py` の `TAG_KEYWORDS` を自分の専門分野に書き換え
- Secrets を各自で設定

---

## トラブルシューティング

| 症状 | 対処 |
|---|---|
| Actions が動かない | Settings → Actions → General で「Allow all actions」に |
| Pages が 404 | Settings → Pages で Source が「GitHub Actions」になっているか確認 |
| メールが来ない | Secrets 名の綴りを確認 (`SMTP_USER` 等) / Gmailのアプリパスワードを再生成 |
| 差分がコミットされない | Settings → Actions → General → Workflow permissions を「Read and write」に |
| 取得件数が減った | 各機関のHTML構造が変わった可能性。`watcher.py` の `scrape_XXX` 関数を修正 |

---

## 運用中のカスタマイズ

**タグを増やす** — `watcher.py` の `TAG_KEYWORDS` 辞書に追加:
```python
TAG_KEYWORDS = {
    "PO/PM系": [...],
    "国際・海外": ["国際", "海外", "SICORP", "ASEAN"],  # ← 追加例
}
```

**実行時刻を変える** — `.github/workflows/daily.yml` の cron を編集:
```yaml
- cron: '0 21 * * *'  # UTC 21:00 = JST 06:00
- cron: '0 23 * * *'  # UTC 23:00 = JST 08:00
```

**対象機関を追加** — `watcher.py` に `scrape_xxx()` を追加して `SCRAPERS` に登録

---

## 費用

**Public リポジトリなら完全無料。**
- GitHub Actions: Public は無制限、Private は月 2000 分（1回3分×30日=90分なので余裕）
- GitHub Pages: 完全無料
- Gmail SMTP: 無料
