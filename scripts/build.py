#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z世代 Signal Atlas - Build Script
data/zgene.docx -> dist/index.html を自動生成する

ヘッダー形式（統一後）:
  週次記事: YYYY/MM/DD-MM/DD Z世代・若年層関連記事と考察
  週次考察: YYYY/MM/DD-MM/DD 週次考察  ← 総論/期間定義
  月次考察: YYYY/MM 月次考察
  四半期:   YYYY/QN 四半期考察
  年次考察: YYYY 年次考察
  ※ 先頭に「# 」が付く場合もある
"""

import os, re, json, glob, html as H

# ── docx -> テキスト ───────────────────────────────────────
def docx_to_text(path):
    from docx import Document
    return "\n".join(p.text.strip() for p in Document(path).paragraphs if p.text.strip())

# ── ヘッダー検索（# 付き/なし両対応）────────────────────────
HEADER_RE = r'(?:^|\n)#?\s*'

def find_all(pat, text):
    return list(re.finditer(HEADER_RE + pat, text, re.MULTILINE))

def section_end(text, start, all_headers):
    """start以降の次のヘッダー位置を返す"""
    for h in all_headers:
        if h.start() > start:
            return h.start()
    return len(text)

# ── 共通クリーン ──────────────────────────────────────────
def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'\*\*|\\n|\\\\|\\.', '', str(s))).strip()

# ── 総論・期間定義を抽出 ──────────────────────────────────
def extract_soron_kikan(sec):
    soron = kikan = ''

    # 新形式: ## 総論　\n\n### テーマ
    m = re.search(r'## 総論[\u3000\s]*\n\n### (.{10,150})', sec)
    if m: soron = clean(m.group(1))

    m = re.search(r'## 期間定義[\u3000\s]*\n\n### (.{10,150})', sec)
    if m: kikan = clean(m.group(1))

    # docx_to_text形式: 総論\nテーマ（改行1つ）
    if not soron:
        m = re.search(r'総論\n(.{10,150})(?:\n|$)', sec)
        if m:
            t = clean(m.group(1)).lstrip('「').rstrip('」')
            if 10 <= len(t) <= 150 and 'http' not in t:
                soron = t

    if not kikan:
        m = re.search(r'期間定義\n(.{10,120})(?:\n|$)', sec)
        if m:
            t = clean(m.group(1)).lstrip('「').rstrip('」')
            if 10 <= len(t) <= 120 and 'http' not in t:
                kikan = t

    # フォールバック（複数パターン対応）
    if not soron:
        for pat in [
            r'総論[\u3000\s]*\n\n「(.{10,150})」',
            r'総論[\u3000\s]*\n\n(.{10,150}?)(?:\n\n|$)',
            r'総論[\u3000](.{10,150}?)(?:\n\n|\Z)',
            r'\*\*総論[\u3000\s](.{10,150}?)\*\*',
            r'総論\n\n(.{10,150}?)(?:\n\n|\Z)',
            r'👉\s*\n総論\*\*(.{10,200}?)\*\*',
            r'総論\*\*(.{10,200}?)\*\*',
        ]:
            m = re.search(pat, sec, re.DOTALL)
            if m:
                t = clean(m.group(1)).lstrip('「').rstrip('」')
                if 10 <= len(t) <= 150 and 'http' not in t:
                    soron = t
                    break

    if not kikan:
        for pat in [
            r'期間定義[\u3000\s]*\n\n「(.{10,120})」',
            r'期間定義[\u3000\s]*\n\n(.{10,120}?)(?:\n\n|$)',
            r'期間定義[\u3000](.{10,120}?)(?:\n\n|\Z)',
        ]:
            m = re.search(pat, sec, re.DOTALL)
            if m:
                t = clean(m.group(1)).lstrip('「').rstrip('」')
                if 10 <= len(t) <= 120 and 'http' not in t:
                    kikan = t
                    break

    return soron, kikan

# ── テーマ抽出 ───────────────────────────────────────────
THEME_COLORS = ['#388E3C','#29B6F6','#AB47BC','#FF7043','#26A69A','#FFA726','#EC407A']

def extract_themes(sec, max_n=7):
    themes = []
    # 番号: **1. 「テーマ」**
    for tm in list(re.finditer(
        r'\*\*\d+\.\s*「(.{5,80})」\*\*\n+(.+?)(?=\*\*\d+\.|##|\Z)',
        sec, re.DOTALL))[:max_n]:
        title = clean(tm.group(1))
        body = re.sub(r'\*\*(?:何が起きている|なぜ|具体行動|兆候|ポイント|重要点|成長の定義|理想|求められる)[^\n]*\*\*\n+', '', tm.group(2))
        body = ' '.join(clean(re.sub(r'\*\*|https?://\S+', '', body)).split())[:100]
        if len(title) > 3: themes.append({'title': title, 'body': body})
    if themes: return themes

    # 丸数字: ① テーマ
    for tm in list(re.finditer(
        r'[①②③④⑤⑥⑦⑧]\s*(?:\*\*)?「?(.{5,80})」?(?:\*\*)?\n+(.+?)(?=[①②③④⑤⑥⑦⑧]|##|\Z)',
        sec, re.DOTALL))[:max_n]:
        title = clean(tm.group(1)).strip('「」')
        body = ' '.join(clean(re.sub(r'\*\*|https?://\S+', '', tm.group(2))).split())[:100]
        if len(title) > 3: themes.append({'title': title, 'body': body})
    return themes

# ── 週次データ抽出 ─────────────────────────────────────────
def extract_weeks(text):
    KEYWORDS = {
        'SNS・デジタル疲れ': ['疲れ','スマホ疲れ','SNS疲れ','デトックス','アナログ回帰','レトロ','BeReal'],
        '推し活・オタク':    ['推し活','推し','オタク','ファン','応援広告'],
        'AI・テクノロジー':  ['AI','生成AI','ChatGPT','Gemini'],
        '消費・購買':        ['消費','購買','買い物','節約','コスパ','タイパ','バズ消費'],
        '働き方・キャリア':  ['就活','キャリア','転職','働き方','離職','新入社員','退職'],
        '価値観・アイデンティティ': ['価値観','アイデンティティ','本音','盛らない','非加工','距離'],
        '恋愛・人間関係':    ['恋愛','結婚','友達','孤独','人間関係'],
        '金融・お金':        ['お金','金融','投資','節約','キャッシュレス','独身税'],
    }

    # 全ヘッダーを収集（境界判定用）
    all_headers = find_all(r'\d{4}/', text)

    # 週次記事ヘッダー
    art_headers = find_all(r'(\d{4}/\d{2}/\d{2}-\d{2}/\d{2}) Z世代[^\n]+記事と考察', text)

    results = []
    for ah in art_headers:
        label = ah.group(1) if ah.lastindex >= 1 else re.search(r'\d{4}/\d{2}/\d{2}-\d{2}/\d{2}', ah.group(0)).group(0)
        s = ah.end()
        e = section_end(text, ah.start() + 1, all_headers)
        articles_sec = text[s:e]

        # 対応する週次考察を探す
        rev_m = re.search(HEADER_RE + re.escape(label) + r' 週次考察', text, re.MULTILINE)
        theme = kikan = ''
        if rev_m:
            rs = rev_m.end()
            re_end = section_end(text, rev_m.start() + 1, all_headers)
            soron, kikan = extract_soron_kikan(text[rs:re_end])
            theme = soron

        articles_count = len(re.findall(r'https?://', articles_sec))
        cats = {c: sum(articles_sec.count(kw) for kw in kws) for c, kws in KEYWORDS.items()}
        results.append({'week': label, 'articles': articles_count, 'theme': theme,
                        'kikan': kikan, 'categories': cats})
    return results

# ── 記事データ抽出 ─────────────────────────────────────────
def extract_articles(text):
    results = []
    all_headers = find_all(r'\d{4}/', text)
    art_headers = find_all(r'(\d{4}/\d{2}/\d{2}-\d{2}/\d{2}) Z世代[^\n]+記事と考察', text)

    for ah in art_headers:
        label = re.search(r'\d{4}/\d{2}/\d{2}-\d{2}/\d{2}', ah.group(0)).group(0)
        s = ah.end()
        e = section_end(text, ah.start() + 1, all_headers)
        sec = text[s:e]
        seen = set()
        for line in sec.split('\n'):
            line = line.strip()
            urls = re.findall(r'https?://[^\s\)\]>]+', line)
            if not urls: continue
            url = urls[0].rstrip(')')
            if url in seen or not url.startswith('http'): continue
            seen.add(url)
            t = re.sub(r'\[\[.+', '', line)
            t = re.sub(r'^[・\-\s★・]+', '', t)
            t = re.sub(r'\{\.underline\}|\[|\]|\*\*', '', t)
            t = re.sub(r'https?://\S+', '', t)
            t = re.sub(r'\s*[-ー]\s*$', '', t.strip().rstrip('\\')).strip()
            if len(t) >= 8 and not t.startswith('```'):
                results.append({'title': t[:120], 'url': url, 'week': label})
    return results

# ── 四半期考察 抽出 ───────────────────────────────────────
PHASE_ICONS  = ['🛡️','⚖️','🎯','🔥','💡','🌊']
PHASE_COLORS = [('#4CAF50','#E8F5E9'),('#F9A825','#FFFDE7'),('#E64A19','#FBE9E7'),('#1565C0','#E3F2FD')]

def extract_quarters(text):
    all_headers = find_all(r'\d{4}/', text)
    q_headers = find_all(r'(\d{4}/Q\d+)[^\n]*(?:四半期|総合)考察', text)
    results = []
    for qh in q_headers:
        label_raw = re.search(r'(\d{4}/Q\d+)', qh.group(0)).group(1)
        year, q = label_raw.split('/Q')
        s = qh.end()
        e = section_end(text, qh.start() + 1, all_headers)
        sec = text[s:e].strip()

        soron, kikan = extract_soron_kikan(sec)
        themes = extract_themes(sec)

        phases = []
        for m in re.finditer(r'(\d+)月：(\S+フェーズ)\n(.+?)キーワード[：:]\s*\*\*?([^\n*]+)\*\*?', sec, re.DOTALL):
            items = re.findall(r'[-・]\s*(.+)', m.group(3).strip())
            phases.append({'month': m.group(1)+'月', 'name': m.group(2),
                           'items': [x.strip() for x in items[:4]], 'kw': m.group(4).strip()})

        wrap_m = re.search(r'Z世代は「拡張社会」を終わらせ[、,]\s*\n?「(.+?)」を作り始めた', sec)
        wrap = wrap_m.group(0).replace('\n', '') if wrap_m else ''

        results.append({'label': '{}年Q{}'.format(year, q), 'year': year, 'q_num': q,
                        'soron': soron, 'kikan': kikan, 'oneliner': kikan,
                        'phases': phases, 'themes': themes, 'wrap': wrap})
    results.sort(key=lambda x: x['label'], reverse=True)
    return results

# ── 月次考察 抽出 ─────────────────────────────────────────
def extract_monthly_reviews(text):
    all_headers = find_all(r'\d{4}/', text)
    m_headers = find_all(r'(\d{4}/\d{2}) 月次考察', text)
    results = []
    seen = set()
    for mh in m_headers:
        label_raw = re.search(r'\d{4}/\d{2}', mh.group(0)).group(0)
        if label_raw in seen: continue
        seen.add(label_raw)
        s = mh.end()
        e = section_end(text, mh.start() + 1, all_headers)
        sec = text[s:e].strip()

        soron, kikan = extract_soron_kikan(sec)
        themes = extract_themes(sec)

        wrap_m = re.search(r'## (.{10,80})\n\n## 一言でいうと', sec)
        wrap = wrap_m.group(1) if wrap_m else ''
        ol_m = re.search(r'一言でいうと\n\n### (.{10,80})', sec)
        oneliner = ol_m.group(1) if ol_m else kikan

        year, mon = label_raw.split('/')
        display = '{}年{}月'.format(year, int(mon))
        results.append({'label': display, 'soron': soron, 'kikan': kikan,
                        'themes': themes, 'wrap': wrap, 'oneliner': oneliner, 'phases': []})

    results.sort(key=lambda x: x['label'], reverse=True)
    return results

# ── 年次考察 抽出 ─────────────────────────────────────────
def extract_annual_reviews(text):
    all_headers = find_all(r'\d{4}/', text)
    a_headers = find_all(r'(\d{4}) 年次考察', text)
    results = []
    for ah in a_headers:
        year = re.search(r'\d{4}', ah.group(0)).group(0)
        s = ah.end()
        # 年次考察は週次記事ヘッダーで終端
        next_art = re.search(HEADER_RE + r'\d{4}/\d{2}/\d{2}', text[s:], re.MULTILINE)
        e = s + next_art.start() if next_art else len(text)
        sec = text[s:e].strip()

        soron, kikan = extract_soron_kikan(sec)
        themes = extract_themes(sec)

        wrap_m = re.search(r'\*\*7\.[^\n]+\*\*\n+(.{20,200}?)(?:\n\n|\Z)', sec, re.DOTALL)
        wrap = clean(wrap_m.group(1))[:120] if wrap_m else ''

        results.append({'label': '{}年 年次考察'.format(year), 'year': year,
                        'soron': soron, 'kikan': kikan, 'oneliner': kikan,
                        'themes': themes, 'wrap': wrap, 'phases': []})
    results.sort(key=lambda x: x['year'], reverse=True)
    return results

# ── アコーディオンHTML生成 ─────────────────────────────────
def build_accordion_html(items, id_prefix, color_primary='var(--green)'):
    if not items:
        return '<div style="color:#888;padding:20px;font-size:14px">データがまだありません</div>'

    parts = []
    for i, q in enumerate(items):
        qid = '{}-{}'.format(id_prefix, i)
        is_open = (i == 0)
        label   = H.escape(q['label'])
        soron   = H.escape(q.get('soron', ''))
        kikan   = H.escape(q.get('kikan', ''))
        oneliner = H.escape(q.get('oneliner', ''))
        subtitle = oneliner if oneliner else (kikan if kikan else label + 'の考察')

        html  = '<div class="q-accordion" id="{}">\n'.format(qid)
        html += '  <div class="q-header" onclick="toggleQ(\'{}\')">\n'.format(qid)
        html += '    <div style="display:flex;align-items:center;gap:12px;flex:1;flex-wrap:wrap">\n'
        html += '      <span style="background:{};color:#fff;font-size:11px;font-weight:900;padding:4px 12px;border-radius:12px">{}</span>\n'.format(color_primary, label)
        html += '      <span style="font-size:13px;font-weight:700;color:var(--tx)">{}</span>\n'.format(subtitle)
        html += '    </div>\n'
        html += '    <span class="q-chevron" id="{}-chev">{}</span>\n'.format(qid, '▲' if is_open else '▼')
        html += '  </div>\n'
        html += '  <div class="q-body" id="{}-body" style="display:{}">\n'.format(qid, 'block' if is_open else 'none')

        # 総論 + 期間定義
        if soron or kikan:
            html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px;margin-bottom:16px">\n'
            if soron:
                html += '      <div style="font-size:10px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">📌 総論</div>\n'
                html += '      <div style="font-size:14px;font-weight:700;color:var(--tx);line-height:1.6;margin-bottom:{}px">{}</div>\n'.format(10 if kikan else 0, soron)
            if kikan:
                html += '      <div style="background:rgba(255,255,255,0.7);padding:8px 12px;border-radius:8px;font-size:13px;margin-top:8px">💡 期間定義：<strong>{}</strong></div>\n'.format(kikan)
            html += '    </div>\n'

        # 月別フェーズ
        if q.get('phases'):
            html += '    <div style="margin-bottom:16px">\n'
            html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">📊 月別フェーズ</div>\n'
            html += '      <div style="display:flex;gap:10px;flex-wrap:wrap">\n'
            for pi, ph in enumerate(q['phases'][:4]):
                col, bg = PHASE_COLORS[pi % len(PHASE_COLORS)]
                html += '        <div style="background:#fff;border-radius:12px;padding:14px;border:1.5px solid {};flex:1;min-width:150px">\n'.format(bg)
                html += '          <div style="font-size:18px;margin-bottom:5px">{}</div>\n'.format(PHASE_ICONS[pi % len(PHASE_ICONS)])
                html += '          <div style="font-size:12px;font-weight:900;color:{};margin-bottom:4px">{}</div>\n'.format(col, H.escape(ph['name']))
                html += '          <div style="font-size:11px;color:var(--ts);line-height:1.6;margin-bottom:5px">{}</div>\n'.format('／'.join(H.escape(x) for x in ph['items']))
                html += '          <div style="background:{};padding:4px 9px;border-radius:8px;font-size:11px;font-weight:700;color:{}">KW：{}</div>\n'.format(bg, col, H.escape(ph['kw']))
                html += '        </div>\n'
            html += '      </div>\n    </div>\n'

        # テーマ別考察
        if q.get('themes'):
            html += '    <div style="margin-bottom:16px">\n'
            html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">🔍 テーマ別考察</div>\n'
            html += '      <div style="display:flex;flex-direction:column;gap:8px">\n'
            for ti, th in enumerate(q['themes']):
                col = THEME_COLORS[ti % len(THEME_COLORS)]
                num = '①②③④⑤⑥⑦'[ti] if ti < 7 else '•'
                html += '        <div style="background:#fff;border-radius:10px;padding:12px;border:1.5px solid #eee;border-left:3px solid {}">\n'.format(col)
                html += '          <div style="font-size:10px;font-weight:900;color:{};text-transform:uppercase;margin-bottom:4px">{} {}</div>\n'.format(col, num, H.escape(th['title']))
                html += '          <div style="font-size:12px;color:var(--ts);line-height:1.6">{}</div>\n'.format(H.escape(th['body']))
                html += '        </div>\n'
            html += '      </div>\n    </div>\n'

        # 締め
        if q.get('wrap'):
            html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px">\n'
            html += '      <div style="font-size:13px;font-weight:700;color:var(--tx);line-height:1.6">{}</div>\n'.format(H.escape(q['wrap']))
            html += '    </div>\n'

        html += '  </div>\n</div>\n'
        parts.append(html)

    return '\n'.join(parts)

# ── メイン ────────────────────────────────────────────────
def main():
    docx_files = glob.glob('data/*.docx')
    if not docx_files:
        print("❌ data/ フォルダに .docx ファイルが見つかりません"); return

    docx_path = docx_files[0]
    print("📄 読み込み: {}".format(docx_path))

    text            = docx_to_text(docx_path)
    weeks_data      = extract_weeks(text)
    articles_data   = extract_articles(text)
    quarters        = extract_quarters(text)
    monthly_reviews = extract_monthly_reviews(text)
    annual_reviews  = extract_annual_reviews(text)

    themed = sum(1 for w in weeks_data if w['theme'])
    print("   テキスト: {:,} 文字".format(len(text)))
    print("   週数: {}  考察付き: {}  記事: {}  四半期: {}件  月次: {}件  年次: {}件".format(
        len(weeks_data), themed, len(articles_data),
        len(quarters), len(monthly_reviews), len(annual_reviews)))

    data_js  = 'const RAW='      + json.dumps(weeks_data,    ensure_ascii=False, separators=(',', ':')) + ';\n'
    data_js += 'const ARTICLES=' + json.dumps(articles_data, ensure_ascii=False, separators=(',', ':')) + ';'

    tpl_path = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(tpl_path, encoding='utf-8') as f:
        html = f.read()

    html = html.replace('// DATA_PLACEHOLDER',                   data_js)
    html = html.replace('<!-- Q_ACCORDION_PLACEHOLDER -->',       build_accordion_html(quarters,        'q', 'var(--green)'))
    html = html.replace('<!-- MONTHLY_ACCORDION_PLACEHOLDER -->', build_accordion_html(monthly_reviews, 'm', '#29B6F6'))
    html = html.replace('<!-- ANNUAL_ACCORDION_PLACEHOLDER -->',  build_accordion_html(annual_reviews,  'a', '#FF7043'))
    html = html.replace('<!-- Q_COUNT_PLACEHOLDER -->',           str(len(quarters)))
    html = html.replace('<!-- MONTHLY_COUNT_PLACEHOLDER -->',     str(len(monthly_reviews)))
    html = html.replace('<!-- ANNUAL_COUNT_PLACEHOLDER -->',      str(len(annual_reviews)))
    html = html.replace('<!-- WEEK_COUNT_PLACEHOLDER -->',        str(len(weeks_data)))
    html = html.replace('<!-- ARTICLE_COUNT_PLACEHOLDER -->',     '{:,}'.format(len(articles_data)))

    os.makedirs('dist', exist_ok=True)
    out = 'dist/index.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ 生成完了: {} ({}KB)".format(out, os.path.getsize(out) // 1024))

if __name__ == '__main__':
    main()
