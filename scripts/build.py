#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z世代 Signal Atlas - Build Script
docx -> JSON -> HTML を自動生成する

使い方:
  python scripts/build.py

data/zgene.docx を読み込んで dist/index.html を生成する
"""

import os
import re
import json
import glob

# ── docxをmarkdownテキストに変換 ──────────────────────────────
def docx_to_text(path):
    from docx import Document
    doc = Document(path)
    lines = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            lines.append(text)
    return "\n".join(lines)

# ── 週データを抽出 ──────────────────────────────────────────
def extract_weeks(text):
    week_pattern = r'✅ Z世代・若年層関連記事まとめ（(.+?)）'
    weeks = list(re.finditer(week_pattern, text))

    KEYWORDS = {
        'SNS・デジタル疲れ': ['疲れ', 'スマホ疲れ', 'SNS疲れ', 'デトックス', 'アナログ回帰', 'レトロ', 'BeReal'],
        '推し活・オタク':    ['推し活', '推し', 'オタク', 'ファン', '応援広告'],
        'AI・テクノロジー':  ['AI', '生成AI', 'ChatGPT', 'Gemini'],
        '消費・購買':        ['消費', '購買', '買い物', '節約', 'コスパ', 'タイパ', 'バズ消費'],
        '働き方・キャリア':  ['就活', 'キャリア', '転職', '働き方', '離職', '新入社員', '退職'],
        '価値観・アイデンティティ': ['価値観', 'アイデンティティ', '本音', '盛らない', '非加工', '距離'],
        '恋愛・人間関係':    ['恋愛', '結婚', '友達', '孤独', '人間関係'],
        '金融・お金':        ['お金', '金融', '投資', '節約', 'キャッシュレス', '独身税'],
    }

    def extract_theme(section):
        m = re.search(r'週次精読版\n\n「(.+?)」', section)
        if m:
            return m.group(1)
        for marker in ['今週の結論', '今週の総括', '総括（最終）']:
            m = re.search(marker + r'\n+([^\n]{15,100})', section)
            if m:
                t = re.sub(r'\*\*', '', m.group(1)).strip()
                if len(t) > 15:
                    return t
        m = re.search(r'🌐[^\n]*総括[^\n]*\n+([^\n]{15,100})', section)
        if m:
            return re.sub(r'\*\*', '', m.group(1)).strip()
        m = re.search(r'👉\s*「?(.{15,80})」?', section)
        if m:
            return re.sub(r'\*\*', '', m.group(1)).strip()
        idx = section.rfind('総括')
        if idx > 0:
            sub = section[idx:idx+400]
            m = re.search(r'\*\*([^\n*]{20,120})\*\*', sub)
            if m:
                t = m.group(1).strip()
                if len(t) > 15 and 'http' not in t:
                    return t
        return None

    results = []
    for i, w in enumerate(weeks):
        start = w.end()
        end = weeks[i+1].start() if i+1 < len(weeks) else len(text)
        section = text[start:end]

        theme = extract_theme(section)
        articles_count = len(re.findall(r'https?://', section))
        cats = {c: sum(section.count(kw) for kw in kws) for c, kws in KEYWORDS.items()}

        results.append({
            'week': w.group(1),
            'articles': articles_count,
            'theme': theme,
            'categories': cats,
        })

    return results

# ── 記事データを抽出 ──────────────────────────────────────────
def extract_articles(text):
    week_pattern = r'✅ Z世代・若年層関連記事まとめ（(.+?)）'
    weeks = list(re.finditer(week_pattern, text))

    results = []
    for i, w in enumerate(weeks):
        start = w.end()
        end = weeks[i+1].start() if i+1 < len(weeks) else len(text)
        section = text[start:end]
        week_name = w.group(1)

        seen_urls = set()
        for line in section.split('\n'):
            line = line.strip()
            urls = re.findall(r'https?://[^\s\)\]]+', line)
            if not urls:
                continue
            url = urls[0].rstrip(')')
            if url in seen_urls or not url.startswith('http'):
                continue
            seen_urls.add(url)

            title = line
            title = re.sub(r'\[\[.+', '', title)
            title = re.sub(r'^[・\-\s]+', '', title)
            title = re.sub(r'\{\.underline\}|\[|\]|\*\*', '', title)
            title = re.sub(r'https?://\S+', '', title)
            title = re.sub(r'\n', ' ', title).strip().rstrip('\\').strip()
            title = re.sub(r'\s*-\s*$', '', title).strip()

            if len(title) >= 8 and not title.startswith('```'):
                results.append({
                    'title': title[:120],
                    'url': url,
                    'week': week_name,
                })

    return results

# ── Q1考察を抽出 ──────────────────────────────────────────────
def extract_q1(text):
    m = re.search(r'2026年Q1 総合考察.+?\n\n(.+?)(?=✅ Z世代)', text, re.DOTALL)
    if not m:
        return None
    q1_text = m.group(1)

    soron_m = re.search(r'Z世代は「(.+?)」から\n「(.+?)」へ移行した', q1_text)
    soron = soron_m.group(0).replace('\n', '') if soron_m else ''

    oneliner_m = re.search(r'「([^」]{10,60})」が標準になった', q1_text)
    oneliner = '「' + oneliner_m.group(1) + '」が標準になった四半期' if oneliner_m else ''

    return {'soron': soron, 'oneliner': oneliner}

# ── メイン処理 ──────────────────────────────────────────────
def main():
    # docxファイルを探す
    docx_files = glob.glob('data/*.docx')
    if not docx_files:
        print("❌ data/ フォルダに .docx ファイルが見つかりません")
        return

    docx_path = docx_files[0]
    print(f"📄 読み込み: {docx_path}")

    # テキスト抽出
    text = docx_to_text(docx_path)
    print(f"   テキスト: {len(text):,} 文字")

    # データ抽出
    weeks_data = extract_weeks(text)
    articles_data = extract_articles(text)
    q1_data = extract_q1(text)

    themed = sum(1 for w in weeks_data if w['theme'])
    print(f"   週数: {len(weeks_data)}  考察付き: {themed}  記事: {len(articles_data)}")

    # JS データブロック生成
    raw_js = 'const RAW=' + json.dumps(weeks_data, ensure_ascii=False, separators=(',', ':')) + ';'
    articles_js = 'const ARTICLES=' + json.dumps(articles_data, ensure_ascii=False, separators=(',', ':')) + ';'
    data_js = raw_js + '\n' + articles_js

    # テンプレート読み込み
    template_path = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_path, encoding='utf-8') as f:
        html = f.read()

    # データ埋め込み
    html = html.replace('// DATA_PLACEHOLDER', data_js)

    # 出力
    os.makedirs('dist', exist_ok=True)
    out_path = 'dist/index.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"✅ 生成完了: {out_path} ({size_kb}KB)")

if __name__ == '__main__':
    main()
