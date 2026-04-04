#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z世代 Signal Atlas - Build Script
data/zgene.docx -> dist/index.html を自動生成する
"""

import os, re, json, glob, html as H

# ── docx -> テキスト ───────────────────────────────────────
def docx_to_text(path):
    from docx import Document
    return "\n".join(p.text.strip() for p in Document(path).paragraphs if p.text.strip())

# ── 週データ抽出（新旧フォーマット対応）──────────────────────
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

    def get_theme(sec):
        patterns = [
            r'## 総論\n\n### (.{10,120})',
            r'精読版\*\*\n\n\*\*「(.+?)」\*\*',
            r'週次精読版\n\n「(.+?)」',
            r'テーマ\n+###\s*(.{15,120})',
            r'👉\s*\*\*「(.{15,120})」\*\*',
            r'今週の結論\*\*\n\n(.{15,120}?)(?:\n\n-|\Z)',
            r'🌐 総括\n\n## (.{10,100})',
            r'🌐[^\n]*総括[：:]\*\*\n\n.{0,80}「(.{10,80})」',
            r'🌐[^\n]*総括[^\n]*\*\*\n\n\*\*「?(.{10,100})」?\*\*',
            r'🌐[^\n]*総括[^\n]*\*\*\n\n\*\*(.{15,120}?)\*\*',
            r'[年月週]のZ世代は[、,]?\s*\*\*「(.{10,80})」\*\*',
            r'[年月週]のZ世代は[、,]?\s*「(.{10,80})」',
            r'今週のZ世代[^。\n]{0,40}[「"](.{10,80})[」"]',
            r'週次考察\*\*\n\n(.{15,120}?)(?:。|\n\n)',
            r'今週の総括\*\*\n\n(.{15,120}?)(?:。|\n\n)',
            r'今週のZ世代を貫くキーワードは[、,]?\s*「(.{5,60})」',
            r'👉\s*「?(.{15,80})」?',
        ]
        for pat in patterns:
            m = re.search(pat, sec, re.DOTALL)
            if m:
                t = re.sub(r'\*\*|\\n|\\\\|\\.', '', m.group(1)).strip()
                t = re.sub(r'\s+', ' ', t).lstrip('「').rstrip('」')
                if t and t[0] in '」\'"）)、。…':
                    continue
                if 10 <= len(t) <= 120 and 'http' not in t:
                    return t
        return None

    # 新形式
    new_wks = list(re.finditer(r'✅ Z世代・若年層関連記事まとめ（(.+?)）', text))
    # 旧形式（7月・8月）
    old_patterns = [
        (r'\*\*📋 Z世代関連記事一覧と考察（(2025年8月25日〜29日)）\*\*', '2025年8月25日〜29日'),
        (r'\*\*📱 Z世代・α世代関連記事まとめ（(2025年8月18日〜22日)）\*\*', '2025年8月18日〜22日'),
        (r'\*\*🗓 8月前半Z世代[^\n]+考察（(2025年8月1日〜8月15日)）\*\*', '2025年8月1日〜15日'),
        (r'\*\*📱 2025年7月 Z世代[^\n]+まとめ\*\*', '2025年7月'),
    ]

    all_sections = []
    for i, w in enumerate(new_wks):
        s = w.end()
        e = new_wks[i+1].start() if i+1 < len(new_wks) else len(text)
        all_sections.append((w.group(1), s, e))
    for pat, label in reversed(old_patterns):
        m = re.search(pat, text)
        if not m: continue
        s = m.end()
        next_m = re.search(r'\*\*(?:📋|📱|🗓|✅)', text[s:])
        e = s + next_m.start() if next_m else s + 8000
        all_sections.append((label, s, e))

    results = []
    for week_label, s, e in all_sections:
        sec = text[s:e]
        results.append({
            'week': week_label,
            'articles': len(re.findall(r'https?://', sec)),
            'theme': get_theme(sec),
            'categories': {c: sum(sec.count(kw) for kw in kws) for c, kws in KEYWORDS.items()},
        })
    return results

# ── 記事データ抽出 ─────────────────────────────────────────
def extract_articles(text):
    results = []

    def extract_from_section(sec, week_name):
        seen = set()
        for line in sec.split('\n'):
            line = line.strip()
            urls = re.findall(r'https?://[^\s\)\]]+', line)
            if not urls: continue
            url = urls[0].rstrip(')')
            if url in seen or not url.startswith('http'): continue
            seen.add(url)
            t = re.sub(r'\[\[.+', '', line)
            t = re.sub(r'^[・\-\s★]+', '', t)
            t = re.sub(r'\{\.underline\}|\[|\]|\*\*', '', t)
            t = re.sub(r'https?://\S+', '', t)
            t = re.sub(r'\s*-\s*$', '', t.strip().rstrip('\\')).strip()
            if len(t) >= 8 and not t.startswith('```'):
                results.append({'title': t[:120], 'url': url, 'week': week_name})

    new_wks = list(re.finditer(r'✅ Z世代・若年層関連記事まとめ（(.+?)）', text))
    for i, w in enumerate(new_wks):
        s = w.end()
        e = new_wks[i+1].start() if i+1 < len(new_wks) else len(text)
        extract_from_section(text[s:e], w.group(1))

    old_patterns = [
        (r'\*\*📋 Z世代関連記事一覧と考察（(2025年8月25日〜29日)）\*\*', '2025年8月25日〜29日'),
        (r'\*\*📱 Z世代・α世代関連記事まとめ（(2025年8月18日〜22日)）\*\*', '2025年8月18日〜22日'),
        (r'\*\*🗓 8月前半Z世代[^\n]+考察（(2025年8月1日〜8月15日)）\*\*', '2025年8月1日〜15日'),
        (r'\*\*📱 2025年7月 Z世代[^\n]+まとめ\*\*', '2025年7月'),
    ]
    for pat, label in old_patterns:
        m = re.search(pat, text)
        if not m: continue
        s = m.end()
        next_m = re.search(r'\*\*(?:📋|📱|🗓|✅)', text[s:])
        e = s + next_m.start() if next_m else s + 8000
        extract_from_section(text[s:e], label)

    return results

# ── 共通: セクションから総論・テーマ・締めを抽出 ──────────────
PHASE_ICONS  = ['🛡️','⚖️','🎯','🔥','💡','🌊']
PHASE_COLORS = [('#4CAF50','#E8F5E9'),('#F9A825','#FFFDE7'),('#E64A19','#FBE9E7'),('#1565C0','#E3F2FD')]
THEME_COLORS = ['#388E3C','#29B6F6','#AB47BC','#FF7043','#26A69A','#FFA726','#EC407A']

def clean(s):
    return re.sub(r'\s+', ' ', re.sub(r'\*\*|\\n|\\\\|\\.', '', s)).strip()

def extract_soron(sec):
    """総論を複数パターンで抽出"""
    for pat in [
        r'## 総論\n\n### (.{10,200})',          # 新形式
        r'\*\*総論\*\*\n\n\*\*(.{10,200}?)\*\*', # 旧形式bold
        r'総論\n\n\*\*(.{10,200}?)\*\*',
        r'👉\s*\n総論\*\*(.{10,200}?)\*\*',
        r'総論[^\n]*\n\n(.{20,200}?)(?:\n\n|\Z)',
    ]:
        m = re.search(pat, sec, re.DOTALL)
        if m:
            t = clean(m.group(1))
            if 10 <= len(t) <= 200 and 'http' not in t:
                return t
    return ''

def extract_themes_from_section(sec, max_themes=7):
    themes = []
    # 番号付きテーマ
    for tm in list(re.finditer(
        r'(?:\*\*)?(\d+)\.\s*「?(.+?)」?\*\*\n+(.+?)(?=\*\*\d+\.|[①②③④⑤⑥⑦]|\Z)',
        sec, re.DOTALL))[:max_themes]:
        title = clean(tm.group(2))
        body = ' '.join(clean(re.sub(r'\*\*|https?://\S+|何が起きている？|なぜ？|マーケ[^\n]*', '', tm.group(3))).split())[:100]
        if len(title) > 3: themes.append({'title': title, 'body': body})
    if themes: return themes
    # 丸数字テーマ
    for tm in list(re.finditer(
        r'[①②③④⑤⑥⑦⑧]\s*(?:\*\*)?「?(.+?)」?(?:\*\*)?\n+(.+?)(?=[①②③④⑤⑥⑦⑧]|🌐|\Z)',
        sec, re.DOTALL))[:max_themes]:
        title = clean(tm.group(1)).strip('「」')
        body = ' '.join(clean(re.sub(r'\*\*|https?://\S+|🔎[^\n]*\n', '', tm.group(2))).split())[:100]
        if len(title) > 3: themes.append({'title': title, 'body': body})
    return themes

# ── Q総括 抽出 ────────────────────────────────────────────
def extract_quarters(text):
    q_matches = list(re.finditer(r'(\d{4})年Q(\d+)\s*総合考察', text))
    if not q_matches: return []
    fw = re.search(r'✅ Z世代・若年層関連記事まとめ', text)
    end_q = fw.start() if fw else len(text)

    results = []
    for i, qm in enumerate(q_matches):
        year, q_num = qm.group(1), qm.group(2)
        s = qm.start()
        e = q_matches[i+1].start() if i+1 < len(q_matches) else end_q
        sec = text[s:e].strip()

        soron_m = re.search(r'Z世代は「(.+?)」から\n?「(.+?)」へ移行した', sec)
        soron = soron_m.group(0).replace('\n', '') if soron_m else extract_soron(sec)

        ol_m = re.search(r'「([^」]{10,60})」が標準になった', sec)
        oneliner = '「{}」が標準になった四半期'.format(ol_m.group(1)) if ol_m else ''

        phases = []
        for m in re.finditer(r'(\d+)月：(\S+フェーズ)\n(.+?)キーワード[：:]\s*\*\*?([^\n*]+)\*\*?', sec, re.DOTALL):
            items = re.findall(r'[-・]\s*(.+)', m.group(3).strip())
            phases.append({'month': m.group(1)+'月', 'name': m.group(2),
                           'items': [x.strip() for x in items[:4]], 'kw': m.group(4).strip()})

        themes = extract_themes_from_section(sec)

        wrap_m = re.search(r'Z世代は「拡張社会」を終わらせ[、,]\s*\n?「(.+?)」を作り始めた', sec)
        wrap = wrap_m.group(0).replace('\n', '') if wrap_m else ''

        results.append({'label': '{}年Q{}'.format(year, q_num), 'year': year, 'q_num': q_num,
                        'soron': soron, 'oneliner': oneliner, 'phases': phases,
                        'themes': themes, 'wrap': wrap})
    return results

# ── 月次考察 抽出 ─────────────────────────────────────────
def extract_monthly_reviews(text):
    results = []
    seen_labels = set()

    # Q総括の終わりを基点にする
    fw = re.search(r'✅ Z世代・若年層関連記事まとめ', text)
    end_limit = fw.start() if fw else len(text)

    # 月次考察のヘッダーパターン（複数形式）
    month_headers = list(re.finditer(r'🧠 (\d{4}年\d+月) 月次総合考察', text))

    for i, mh in enumerate(month_headers):
        label = mh.group(1)
        if label in seen_labels: continue
        seen_labels.add(label)
        s = mh.start()
        e = month_headers[i+1].start() if i+1 < len(month_headers) else end_limit
        sec = text[s:e].strip()

        soron = extract_soron(sec)
        themes = extract_themes_from_section(sec)

        # 締め・一言
        wrap_m = re.search(r'## (.{10,80})\n\n## 一言でいうと', sec)
        wrap = wrap_m.group(1) if wrap_m else ''
        ol_m = re.search(r'一言でいうと\n\n### (.{10,80})', sec)
        oneliner = ol_m.group(1) if ol_m else ''

        results.append({'label': label, 'soron': soron, 'themes': themes,
                        'wrap': wrap, 'oneliner': oneliner, 'phases': []})

    results.sort(key=lambda x: x['label'], reverse=True)
    return results

# ── 年次考察 抽出 ─────────────────────────────────────────
def extract_annual_reviews(text):
    results = []
    # 年次考察ヘッダーを探す
    annual_m = list(re.finditer(r'(\d{4})\s*Z世代[^\n]*年次考察', text))
    if not annual_m: return results

    # 次のセクション（Q総括）の位置
    next_major = re.search(r'🧠 \d{4}年Q\d+', text)
    end_limit = next_major.start() if next_major else len(text)

    for i, am in enumerate(annual_m):
        year = am.group(1)
        label = '{}年 年次考察'.format(year)
        s = am.start()
        e = annual_m[i+1].start() if i+1 < len(annual_m) else end_limit
        sec = text[s:e].strip()

        # 総論
        soron_m = re.search(r'総論\*\*(.{10,200}?)\*\*', sec)
        soron = clean(soron_m.group(1)) if soron_m else extract_soron(sec)

        themes = extract_themes_from_section(sec)

        # 締め
        wrap_m = re.search(r'7\.\s*(?:\*\*)?2025年を貫く一本の思想\*\*\n+(.{20,200}?)(?:\n\n|\Z)', sec, re.DOTALL)
        wrap = clean(wrap_m.group(1))[:120] if wrap_m else ''

        results.append({'label': label, 'year': year, 'soron': soron,
                        'themes': themes, 'wrap': wrap, 'oneliner': '', 'phases': []})

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
        label = H.escape(q['label'])
        ol = H.escape(q.get('oneliner', '')) if q.get('oneliner') else label + 'の考察'
        soron = H.escape(q.get('soron', ''))

        html  = '<div class="q-accordion" id="{}">\n'.format(qid)
        html += '  <div class="q-header" onclick="toggleQ(\'{}\')">\n'.format(qid)
        html += '    <div style="display:flex;align-items:center;gap:12px;flex:1;flex-wrap:wrap">\n'
        html += '      <span style="background:{};color:#fff;font-size:11px;font-weight:900;padding:4px 12px;border-radius:12px">{}</span>\n'.format(color_primary, label)
        html += '      <span style="font-size:13px;font-weight:700;color:var(--tx)">{}</span>\n'.format(ol)
        html += '    </div>\n'
        html += '    <span class="q-chevron" id="{}-chev">{}</span>\n'.format(qid, '▲' if is_open else '▼')
        html += '  </div>\n'
        html += '  <div class="q-body" id="{}-body" style="display:{}">\n'.format(qid, 'block' if is_open else 'none')

        if soron:
            ol_html = ''
            if q.get('oneliner'):
                ol_html = '<div style="margin-top:8px;background:rgba(255,255,255,0.7);padding:8px 12px;border-radius:8px;font-size:13px">💡 一言：<strong>{}</strong></div>'.format(H.escape(q['oneliner']))
            html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px;margin-bottom:16px">\n'
            html += '      <div style="font-size:10px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">📌 総論</div>\n'
            html += '      <div style="font-size:14px;font-weight:700;color:var(--tx);line-height:1.6">{}</div>{}\n'.format(soron, ol_html)
            html += '    </div>\n'

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
    print("   週数: {}  考察付き: {}  記事: {}  Q総括: {}件  月次: {}件  年次: {}件".format(
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
