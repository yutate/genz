#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z世代 Signal Atlas - Build Script
docx -> JSON -> HTML を自動生成する
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

# ── Q総括を抽出（アコーディオン用） ──────────────────────────────
def extract_quarters(text):
    pattern = r'🧠\s*(\d{4}年Q\d)\s*総合考察.*?\n(.*?)(?=✅\s*Z世代|🧠\s*\d{4}年Q\d\s*総合考察|\Z)'
    matches = re.finditer(pattern, text, re.DOTALL)
    
    quarters = []
    for m in matches:
        q_title = m.group(1)
        q_body = m.group(2).strip()
        
        html_lines = []
        for line in q_body.split('\n'):
            line = line.strip()
            if not line:
                continue
                
            if re.match(r'^[📊🔍🌐🔮📌]', line):
                html_lines.append(f'<h3 style="margin-top:28px; margin-bottom:14px; color:var(--green-d); font-size:16px; border-bottom: 2px solid var(--green-l); padding-bottom:6px; display:flex; align-items:center; gap:6px;">{line}</h3>')
            elif re.match(r'^[①②③④⑤⑥⑦⑧⑨⑩]', line):
                html_lines.append(f'<h4 style="margin-top:20px; margin-bottom:10px; color:var(--tx); font-size:15px; font-weight:bold; padding-left:8px; border-left:4px solid var(--green);">{line}</h4>')
            elif line.startswith('🔎'):
                html_lines.append(f'<h5 style="margin-top:14px; margin-bottom:6px; color:var(--ts); font-size:13px; font-weight:bold;">{line}</h5>')
            elif line.startswith('👉'):
                html_lines.append(f'<div style="margin:12px 0; padding:12px 16px; background:var(--green-xl); border-radius:10px; font-weight:bold; color:var(--green-d); font-size:13px; box-shadow:0 2px 8px rgba(76,175,80,0.1);">{line}</div>')
            elif line.startswith('・') and 'http' in line:
                parts = line.split('http')
                if len(parts) >= 2:
                    url = 'http' + parts[1]
                    title = parts[0].strip('・ ')
                    html_lines.append(f'<div style="margin-bottom:6px; font-size:12px; padding-left:12px; position:relative;"><span style="position:absolute; left:0; color:var(--ts);">•</span><a href="{url}" target="_blank" style="color:var(--green-d); text-decoration:none; font-weight:500;">{title}</a></div>')
                else:
                    html_lines.append(f'<div style="line-height:1.7; margin-bottom:6px; font-size:13px; color:var(--tx);">{line}</div>')
            else:
                html_lines.append(f'<div style="line-height:1.7; margin-bottom:6px; font-size:13px; color:var(--tx);">{line}</div>')
                
        quarters.append({
            'title': q_title,
            'html': ''.join(html_lines)
        })
        
    return quarters

# ── メイン処理 ──────────────────────────────────────────────
def main():
    docx_files = glob.glob('data/*.docx')
    if not docx_files:
        print("❌ data/ フォルダに .docx ファイルが見つかりません")
        return

    docx_path = docx_files[0]
    print(f"📄 読み込み: {docx_path}")

    text = docx_to_text(docx_path)
    print(f"   テキスト: {len(text):,} 文字")

    weeks_data = extract_weeks(text)
    articles_data = extract_articles(text)
    quarters_data = extract_quarters(text)

    themed = sum(1 for w in weeks_data if w['theme'])
    print(f"   週数: {len(weeks_data)}  考察付き: {themed}  記事: {len(articles_data)}  Q総括: {len(quarters_data)}")

    raw_js = 'const RAW=' + json.dumps(weeks_data, ensure_ascii=False, separators=(',', ':')) + ';'
    articles_js = 'const ARTICLES=' + json.dumps(articles_data, ensure_ascii=False, separators=(',', ':')) + ';'
    quarters_js = 'const QUARTERS=' + json.dumps(quarters_data, ensure_ascii=False, separators=(',', ':')) + ';'
    data_js = raw_js + '\n' + articles_js + '\n' + quarters_js

    template_path = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(template_path, encoding='utf-8') as f:
        html = f.read()

    html = html.replace('// DATA_PLACEHOLDER', data_js)

    os.makedirs('dist', exist_ok=True)
    out_path = 'dist/index.html'
    with open(out_path, 'w', encoding='utf-8') as f:
        f.write(html)

    size_kb = os.path.getsize(out_path) // 1024
    print(f"✅ 生成完了: {out_path} ({size_kb}KB)")

if __name__ == '__main__':
    main()

