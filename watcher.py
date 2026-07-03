#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Funding-Related Talent Recruitment Watcher (Phase 1 PoC)
======================================================================
7つの国立研究開発法人 + JREC-IN Portal から
「ファンディング関連業務を担う人材」の公募情報を日次収集し、
差分検知 + タグ付け + 一覧化 + メール本文プレビュー生成を行う。

対象: 京セラ「経験活用型社外出向スキーム」対象社員
初期利用者: 本人 (PoC) → 後にジョブ産雇/上司/人事/他対象者に横展開

Author: PoC for 京セラ社内利用
"""

import re
import json
import sqlite3
import hashlib
import datetime as dt
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

# ---------------------------------------------------------------------------
# 設定
# ---------------------------------------------------------------------------
BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "recruitment.db"
OUTPUT_DIR = BASE_DIR / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0 Safari/537.36 "
        "FundingWatcher/1.0 (personal-research-use)"
    ),
    "Accept-Language": "ja,en;q=0.8",
}
TIMEOUT = 30

# --- タグ体系（本人プロフィールに合わせて調整可能） ---
TAG_KEYWORDS = {
    "PO/PM系": [
        "プログラムオフィサー", "プログラム・オフィサー", "PO",
        "プログラムマネージャー", "プログラム・マネージャー", "PM",
        "研究開発マネジメント", "研究開発マネージャ",
    ],
    "URA/研究推進": [
        "URA", "リサーチ・アドミニストレーター", "リサーチアドミニストレーター",
        "研究推進", "研究支援", "研究企画",
    ],
    "ファンディング": [
        "ファンディング", "研究資金", "助成", "配分", "公募運営",
        "審査", "研究開発マネジメント", "事業推進",
    ],
    "産学連携/技術移転": [
        "産学連携", "産学官連携", "技術移転", "知財",
        "スタートアップ", "起業支援",
    ],
    "ディープテック": [
        "ディープテック", "先端技術", "深い技術", "コア技術",
        "研究企画",
    ],
}

# 対象年齢層 (51-65歳) との整合性: 若手/新卒公募は自動除外
EXCLUDE_KEYWORDS = [
    "新卒", "若手", "テニュアトラック", "ポスドク", "博士研究員",
    "特別研究員", "パートタイマー", "アルバイト", "学生",
]


# ---------------------------------------------------------------------------
# DB
# ---------------------------------------------------------------------------
def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS recruitments (
            id TEXT PRIMARY KEY,           -- URL + タイトルのハッシュ
            agency TEXT NOT NULL,          -- 機関名
            title TEXT NOT NULL,           -- 職名/タイトル
            url TEXT NOT NULL,             -- 詳細URL
            deadline TEXT,                 -- 締切 (文字列そのまま)
            location TEXT,                 -- 勤務地
            tags TEXT,                     -- カンマ区切りタグ
            excluded INTEGER DEFAULT 0,    -- 51-65向け除外フラグ
            first_seen TEXT NOT NULL,      -- 初回検知日
            last_seen TEXT NOT NULL,       -- 最終確認日
            snapshot_hash TEXT             -- 本文ハッシュ (差分検知用)
        )
    """)
    conn.commit()
    return conn


def make_id(url: str, title: str) -> str:
    return hashlib.sha256(f"{url}|{title}".encode("utf-8")).hexdigest()[:16]


def apply_tags(text: str) -> list[str]:
    """タイトル+本文からタグを付与"""
    tags = []
    for tag, kws in TAG_KEYWORDS.items():
        if any(kw in text for kw in kws):
            tags.append(tag)
    return tags


def is_excluded(text: str) -> bool:
    """51-65歳対象外の求人を判定"""
    return any(kw in text for kw in EXCLUDE_KEYWORDS)


# ---------------------------------------------------------------------------
# スクレイパ (機関ごと)
# ---------------------------------------------------------------------------
def fetch(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        r.raise_for_status()
        # 文字化け対策: charsetヒントから正規化
        if r.encoding.lower() == "iso-8859-1":
            r.encoding = r.apparent_encoding
        return r.text
    except Exception as e:
        print(f"  [ERROR] {url}: {e}")
        return None


def scrape_jst() -> list[dict]:
    """JST 採用情報一覧 (テーブル構造)"""
    url = "https://www.jst.go.jp/saiyou/"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tbl in soup.find_all("table"):
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 4:
                continue
            # JSTのテーブル: [業務内容/リンク, 職名, 部署, 勤務地, 締切日, 掲載日]
            title_cell = tds[0]
            a = title_cell.find("a")
            link = urljoin(url, a["href"]) if a and a.get("href") else url
            title = " / ".join(t.get_text(strip=True) for t in tds[:2] if t.get_text(strip=True))
            location = tds[3].get_text(strip=True) if len(tds) > 3 else ""
            deadline = tds[4].get_text(strip=True) if len(tds) > 4 else ""
            if title:
                out.append({
                    "agency": "JST",
                    "title": title,
                    "url": link,
                    "location": location,
                    "deadline": deadline,
                })
    return out


def scrape_nedo() -> list[dict]:
    """NEDO 採用情報一覧"""
    url = "https://www.nedo.go.jp/saiyou/saiyoulist.html"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tbl in soup.find_all("table"):
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            text = tr.get_text(" ", strip=True)
            a = tr.find("a")
            link = urljoin(url, a["href"]) if a and a.get("href") else url
            # NEDOはリンクを含む行を採用中と判定
            if a and "募集" in text or "公募" in text:
                title = a.get_text(strip=True) if a else tds[0].get_text(strip=True)
                if title and "募集要領" not in title and "マイページ" not in title:
                    out.append({
                        "agency": "NEDO",
                        "title": f"{tds[0].get_text(strip=True)} - {title}"[:200],
                        "url": link,
                        "location": "",
                        "deadline": "",
                    })
    return out


def scrape_jaxa() -> list[dict]:
    """JAXA キャリア採用 (SNARシステム経由・render_js無しで試行)"""
    # SNARポータルは動的だが、機関側の総合ページから可能な範囲で拾う
    url = "https://www.jaxa.jp/about/employ/career_j.html"
    html = fetch(url)
    if not html:
        return []
    # SNARが取れれば理想だが、render_js無しでは限界がある
    # ここでは既知の応募窓口URLを提示するのみ (実運用ではSelenium/Playwright併用推奨)
    return [{
        "agency": "JAXA",
        "title": "【要確認】JAXAキャリア採用 (SNARポータル動的取得のため定期閲覧推奨)",
        "url": "https://jaxacareer.snar.jp/index.aspx",
        "location": "",
        "deadline": "随時 (掲載日順)",
    }]


def scrape_riken() -> list[dict]:
    """理研 採用情報検索 (th行の変則テーブル構造)"""
    url = "https://www.riken.jp/careers/openings/"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tbl in soup.find_all("table"):
        for tr in tbl.find_all("tr"):
            # 理研は th=部署(1) + td=主宰者/職種/締切/勤務地(4)
            th = tr.find("th")
            tds = tr.find_all("td")
            if not th or len(tds) < 4:
                continue
            a = tds[1].find("a") if len(tds) > 1 else None
            if not a:
                continue
            dept = th.get_text(" ", strip=True)
            pi = tds[0].get_text(" ", strip=True)
            title = a.get_text(strip=True)
            link = urljoin(url, a["href"])
            deadline = tds[2].get_text(" ", strip=True)
            location = tds[3].get_text(" ", strip=True)
            out.append({
                "agency": "理研",
                "title": f"{dept} - {title}" + (f" (PI: {pi})" if pi else ""),
                "url": link,
                "location": location,
                "deadline": deadline,
            })
    return out


def scrape_aist() -> list[dict]:
    """AIST 外部資金型プロジェクト公募課題 (研究員系だが業務系タグも一部含む)"""
    urls = [
        "https://www.aist.go.jp/aist_j/humanres/02kenkyu/task.html",
        "https://www.aist.go.jp/aist_j/humanres/02kenkyu/task_project.html",
    ]
    out = []
    seen = set()
    for url in urls:
        html = fetch(url)
        if not html:
            continue
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            title = a.get_text(strip=True)
            if not title or len(title) < 10:
                continue
            link = urljoin(url, a["href"])
            key = (title, link)
            if key in seen:
                continue
            if any(kw in title for kw in ["公募", "募集", "採用", "研究員", "職員"]):
                seen.add(key)
                out.append({
                    "agency": "AIST",
                    "title": title[:200],
                    "url": link,
                    "location": "",
                    "deadline": "",
                })
    return out


def scrape_nict() -> list[dict]:
    """NICT 有期一般職公募 (事務・研究支援)"""
    url = "https://www.nict.go.jp/employment/yuuki-ippan.html"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    for tbl in soup.find_all("table"):
        for tr in tbl.find_all("tr"):
            tds = tr.find_all("td")
            if len(tds) < 2:
                continue
            a = tr.find("a")
            if not a:
                continue
            title = a.get_text(strip=True)
            if not title:
                continue
            link = urljoin(url, a["href"])
            text = tr.get_text(" ", strip=True)
            # 締切っぽいトークン抽出
            m = re.search(r"(20\d{2}[年/\-\.]\d{1,2}[月/\-\.]\d{1,2})", text)
            deadline = m.group(1) if m else ""
            out.append({
                "agency": "NICT",
                "title": title[:200],
                "url": link,
                "location": "",
                "deadline": deadline,
            })
    return out


def scrape_jamstec() -> list[dict]:
    """JAMSTEC は中途/経験者向け一覧が薄い → JREC-INのJAMSTEC検索で代替"""
    url = "https://jrecin.jst.go.jp/seek/SeekJorSearch?fn=0&keyword_and=JAMSTEC"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"SeekJorDetail")):
        title = a.get_text(strip=True)
        href = a["href"]
        if not title or len(title) < 5 or href in seen:
            continue
        seen.add(href)
        link = urljoin("https://jrecin.jst.go.jp/seek/", href)
        parent = a.find_parent(["div", "li", "tr", "table"]) or a.parent
        surrounding = parent.get_text(" ", strip=True) if parent else ""
        m_dead = re.search(r"(20\d{2}[年/\-\.]\s*\d{1,2}[月/\-\.]\s*\d{1,2})", surrounding)
        deadline = m_dead.group(1) if m_dead else ""
        out.append({
            "agency": "JAMSTEC(via JREC-IN)",
            "title": title[:200],
            "url": link,
            "location": "",
            "deadline": deadline,
        })
    return out


def scrape_jrecin_ura() -> list[dict]:
    """JREC-IN 横串: 研究管理者相当 (URA等) 公募一覧"""
    url = "https://jrecin.jst.go.jp/seek/SeekJorSearch?fn=0&jobkind=00018"
    html = fetch(url)
    if not html:
        return []
    soup = BeautifulSoup(html, "html.parser")
    out = []
    # JREC-IN の各求人は SeekJorDetail への <a> を持つ
    seen = set()
    for a in soup.find_all("a", href=re.compile(r"SeekJorDetail")):
        title = a.get_text(strip=True)
        href = a["href"]
        if not title or len(title) < 5 or href in seen:
            continue
        seen.add(href)
        link = urljoin("https://jrecin.jst.go.jp/seek/", href)
        # 周辺テキストから機関名/締切を推定
        parent = a.find_parent(["div", "li", "tr"]) or a.parent
        surrounding = parent.get_text(" ", strip=True) if parent else ""
        m_agency = re.search(r"(国立研究開発法人[^\s、,。]+|[^\s、,。]+大学|[^\s、,。]+機構)", surrounding)
        agency = m_agency.group(1) if m_agency else ""
        m_dead = re.search(r"(20\d{2}[年/\-\.]\s*\d{1,2}[月/\-\.]\s*\d{1,2})", surrounding)
        deadline = m_dead.group(1) if m_dead else ""
        out.append({
            "agency": f"JREC-IN URA{' / ' + agency if agency else ''}",
            "title": title[:200],
            "url": link,
            "location": "",
            "deadline": deadline,
        })
    return out


SCRAPERS = [
    ("JST", scrape_jst),
    ("NEDO", scrape_nedo),
    ("JAXA", scrape_jaxa),
    ("理研", scrape_riken),
    ("AIST", scrape_aist),
    ("NICT", scrape_nict),
    ("JAMSTEC", scrape_jamstec),
    ("JREC-IN(URA)", scrape_jrecin_ura),
]


# ---------------------------------------------------------------------------
# メインロジック
# ---------------------------------------------------------------------------
def run_daily():
    conn = init_db()
    cur = conn.cursor()
    today = dt.date.today().isoformat()

    print(f"=== 日次収集開始: {today} ===\n")
    all_items = []
    new_items = []
    updated_items = []

    for name, fn in SCRAPERS:
        print(f"[{name}] 取得中...")
        try:
            items = fn()
        except Exception as e:
            print(f"  [ERROR] {name} scraping failed: {e}")
            items = []
        print(f"  → {len(items)} 件")

        for it in items:
            item_id = make_id(it["url"], it["title"])
            text_for_tag = f"{it['title']} {it.get('location', '')}"
            tags = apply_tags(text_for_tag)
            excluded = is_excluded(text_for_tag)
            snap = hashlib.sha256(json.dumps(it, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:16]

            row = cur.execute("SELECT snapshot_hash, first_seen FROM recruitments WHERE id=?", (item_id,)).fetchone()
            if row is None:
                cur.execute("""INSERT INTO recruitments
                    (id, agency, title, url, deadline, location, tags, excluded, first_seen, last_seen, snapshot_hash)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                    (item_id, it["agency"], it["title"], it["url"],
                     it.get("deadline", ""), it.get("location", ""),
                     ",".join(tags), int(excluded), today, today, snap))
                new_items.append({**it, "tags": tags, "excluded": excluded, "id": item_id})
            else:
                old_snap, first_seen = row
                if old_snap != snap:
                    cur.execute("""UPDATE recruitments SET deadline=?, location=?, tags=?, excluded=?,
                                   last_seen=?, snapshot_hash=? WHERE id=?""",
                        (it.get("deadline", ""), it.get("location", ""),
                         ",".join(tags), int(excluded), today, snap, item_id))
                    updated_items.append({**it, "tags": tags, "excluded": excluded, "id": item_id})
                else:
                    cur.execute("UPDATE recruitments SET last_seen=? WHERE id=?", (today, item_id))
            all_items.append({**it, "tags": tags, "excluded": excluded, "id": item_id})

    conn.commit()
    conn.close()

    print(f"\n=== 収集結果 ===")
    print(f"合計: {len(all_items)} 件 / 新規: {len(new_items)} / 更新: {len(updated_items)}")

    # 出力
    write_csv(all_items)
    write_html_dashboard(all_items)
    write_email_preview(new_items, updated_items)

    return all_items, new_items, updated_items


def write_csv(items):
    import csv
    path = OUTPUT_DIR / f"recruitments_{dt.date.today().isoformat()}.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f)
        w.writerow(["機関", "職種/タイトル", "勤務地", "締切", "タグ", "対象外", "URL"])
        # タグ付き優先ソート
        items_sorted = sorted(items, key=lambda x: (x.get("excluded", False), -len(x.get("tags", [])), x["agency"]))
        for it in items_sorted:
            w.writerow([
                it["agency"], it["title"], it.get("location", ""),
                it.get("deadline", ""), ",".join(it.get("tags", [])),
                "○" if it.get("excluded") else "",
                it["url"],
            ])
    print(f"CSV出力: {path}")


AGENCY_SOURCE_URLS = {
    "JST": "https://www.jst.go.jp/saiyou/",
    "NEDO": "https://www.nedo.go.jp/saiyou/saiyoulist.html",
    "JAXA": "https://www.jaxa.jp/about/employ/career_j.html",
    "理研": "https://www.riken.jp/careers/openings/",
    "AIST": "https://www.aist.go.jp/aist_j/humanres/02kenkyu/task.html",
    "NICT": "https://www.nict.go.jp/employment/yuuki-ippan.html",
    "JAMSTEC(via JREC-IN)": "https://jrecin.jst.go.jp/seek/SeekJorSearch?fn=0&keyword_and=JAMSTEC",
    "JREC-IN(URA)": "https://jrecin.jst.go.jp/seek/SeekJorSearch?fn=0&jobkind=00018",
}


def write_html_dashboard(items):
    path = OUTPUT_DIR / "dashboard.html"
    matched = [it for it in items if it.get("tags") and not it.get("excluded")]
    others  = [it for it in items if not it.get("tags") and not it.get("excluded")]
    excluded = [it for it in items if it.get("excluded")]

    def row(it):
        tag_html = " ".join(f'<span class="tag">{t}</span>' for t in it.get("tags", []))
        return f"""<tr>
          <td>{it['agency']}</td>
          <td><a href="{it['url']}" target="_blank">{it['title']}</a></td>
          <td>{it.get('location','')}</td>
          <td>{it.get('deadline','')}</td>
          <td>{tag_html}</td>
        </tr>"""

    html = f"""<!DOCTYPE html><html lang="ja"><head><meta charset="UTF-8">
<title>ファンディング人材公募ダッシュボード</title>
<style>
body {{ font-family: sans-serif; margin: 20px; color:#222; }}
h1 {{ font-size: 22px; }}
h2 {{ font-size: 16px; margin-top: 24px; color: #444;
      border-left: 4px solid #0F7FFF; padding-left: 8px; }}
table {{ border-collapse: collapse; width: 100%; font-size: 13px; }}
th, td {{ border: 1px solid #ddd; padding: 6px; vertical-align: top; }}
th {{ background: #f5f7fa; }}
.tag {{ display:inline-block; padding:2px 8px; margin:1px;
        border-radius:8px; background:#e6f2ff; color:#0655a3; font-size:11px;}}
.summary {{ background:#f0f6ff; padding:10px; border-radius:8px; margin: 16px 0;}}
a {{ color:#0655a3; }}
</style></head><body>
<h1>ファンディング関連人材公募ダッシュボード</h1>
<div class="summary">
  最終更新: {dt.date.today().isoformat()} （GitHub Actions により毎日06:00 JST自動更新）<br>
  合計: {len(items)} 件 /
  <b>タグ一致: {len(matched)} 件</b> /
  対象外(若手・新卒等): {len(excluded)} 件
  <br><br>
  <b>取得元ページ（手動確認用）:</b>
  {" | ".join(f'<a href="{u}" target="_blank">{a}</a>' for a, u in AGENCY_SOURCE_URLS.items())}
</div>

<h2>◎ タグ一致 (優先閲覧)</h2>
<table>
  <thead><tr><th>機関</th><th>職種/タイトル</th><th>勤務地</th><th>締切</th><th>タグ</th></tr></thead>
  <tbody>{"".join(row(it) for it in matched)}</tbody>
</table>

<h2>△ タグ未一致 (参考)</h2>
<table>
  <thead><tr><th>機関</th><th>職種/タイトル</th><th>勤務地</th><th>締切</th><th>タグ</th></tr></thead>
  <tbody>{"".join(row(it) for it in others[:50])}</tbody>
</table>
{'<p>...(残り ' + str(len(others)-50) + ' 件は省略)</p>' if len(others) > 50 else ''}

<h2>× 対象外 (若手・新卒等)</h2>
<table>
  <thead><tr><th>機関</th><th>職種/タイトル</th><th>勤務地</th><th>締切</th><th>タグ</th></tr></thead>
  <tbody>{"".join(row(it) for it in excluded[:30])}</tbody>
</table>
{'<p>...(残り ' + str(len(excluded)-30) + ' 件は省略)</p>' if len(excluded) > 30 else ''}

</body></html>"""
    path.write_text(html, encoding="utf-8")
    print(f"HTMLダッシュボード: {path}")


def write_email_preview(new_items, updated_items):
    """メール本文プレビュー (実送信は SMTP を後で追加)"""
    path = OUTPUT_DIR / "email_preview.txt"
    lines = []
    lines.append(f"件名: [公募Watch] {dt.date.today()} 新規 {len(new_items)} / 更新 {len(updated_items)}")
    lines.append("=" * 60)
    lines.append("")
    lines.append("▼ 新規公募 (タグ一致優先)")
    lines.append("-" * 60)
    new_sorted = sorted(new_items, key=lambda x: (x.get("excluded", False), -len(x.get("tags", []))))
    for it in new_sorted[:20]:
        mark = "◎" if it.get("tags") and not it.get("excluded") else ("×" if it.get("excluded") else "△")
        tags = ",".join(it.get("tags", [])) or "-"
        lines.append(f"{mark} [{it['agency']}] {it['title']}")
        lines.append(f"    タグ: {tags} | 締切: {it.get('deadline','')} | 勤務地: {it.get('location','')}")
        lines.append(f"    {it['url']}")
        lines.append("")

    lines.append("")
    lines.append("▼ 更新公募")
    lines.append("-" * 60)
    for it in updated_items[:10]:
        lines.append(f"・[{it['agency']}] {it['title']}")
        lines.append(f"    {it['url']}")

    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"メール本文プレビュー: {path}")


if __name__ == "__main__":
    run_daily()
