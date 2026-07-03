# ファンディング関連人材公募ウォッチャー

京セラ「経験活用型社外出向スキーム」対象者（51-65歳）向けに、7つの国立研究開発法人 + JREC-IN Portal から **ファンディング関連業務の人材公募** を毎日自動収集するツール。

## 特徴
- 🔄 **完全自動**: GitHub Actions で毎朝 06:00 (JST) 実行
- 🌐 **誰でも閲覧**: GitHub Pages で Web 公開、URL 共有で関係者全員が見られる
- ✉️ **本人へ通知**: 新規公募があればメール送信（Gmail SMTP）
- 🏷️ **自動タグ付け**: PO/PM系・URA/研究推進・ファンディング・産学連携 等
- 🚫 **対象外の自動除外**: 新卒・若手・ポスドク・パートタイマーは自動フィルタ
- 💰 **無料**: Public リポジトリなら完全無料

## 対象データ源
| 機関 | 監視URL |
|---|---|
| [JST](https://www.jst.go.jp/saiyou/) | 採用情報一覧 (研究開発マネジメント専門員、PO 等) |
| [NEDO](https://www.nedo.go.jp/saiyou/saiyoulist.html) | 採用情報 (プロジェクトマネージャー、事務職員) |
| [JAXA](https://www.jaxa.jp/about/employ/career_j.html) | キャリア採用 |
| [理研](https://www.riken.jp/careers/openings/) | 事務職・研究支援職 |
| [AIST](https://www.aist.go.jp/aist_j/humanres/02kenkyu/task.html) | 外部資金プロジェクト公募 |
| [NICT](https://www.nict.go.jp/employment/yuuki-ippan.html) | 有期一般職 |
| [JAMSTEC](https://jrecin.jst.go.jp/) | JREC-IN 経由 |
| [JREC-IN URA横串](https://jrecin.jst.go.jp/seek/SeekJorSearch?fn=0&jobkind=00018) | 全国のURA公募（漏れ検知） |

## クイックスタート
👉 **[SETUP.md](./SETUP.md)** に非エンジニアでも従える手順を記載（GitHubアカウント作成〜Pages公開まで15分）

## ローカルで試す場合
```bash
pip install requests beautifulsoup4
python watcher.py
# output/dashboard.html をブラウザで開く
```

## タグ体系（カスタマイズ可能）
`watcher.py` の `TAG_KEYWORDS` を編集:
- **PO/PM系** — プログラムオフィサー、研究開発マネジメント
- **URA/研究推進** — リサーチアドミニストレータ、研究企画
- **ファンディング** — 研究資金、公募運営、審査
- **産学連携/技術移転** — 産学官連携、知財、スタートアップ支援
- **ディープテック** — 先端技術、コア技術

## Phase 2 拡張予定
- 締切2週間前の再リマインド
- Web ダッシュボードのフィルタ/ソート UI (JS強化)
- 関係者向け週次サマリメール
- 対象者ごとのプロフィール別タグ設定 (マルチユーザ化)
