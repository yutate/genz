#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z世代 Signal Atlas - Build Script
data/zgene.json -> dist/index.html を自動生成する

JSONスキーマ (v4):
  weekly[]   : articles + analysis.sections (総論/期間定義)
  monthly[]  : summary + period_definition
  quarterly[]: summary + period_definition + sections
  annual[]   : summary + sections
"""

import os, re, json, glob, html as H

# ── JSONを読み込む ─────────────────────────────────────────
def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

# ── 共通クリーン ──────────────────────────────────────────
def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', re.sub(r'\*\*|\\n', '', str(s))).strip()

# ── 週次データ抽出 ─────────────────────────────────────────
def extract_weeks(data):
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

    results = []
    for w in data['weekly']:
        period = w.get('period', {})
        # 表示用ラベル
        key = period.get('key', '')
        label = key.replace('_', ' 〜 ').replace('-', '/') if '_' in key else key

        # 総論・期間定義
        analysis = w.get('analysis') or {}
        theme = ''
        kikan = ''
        summary = ''
        if analysis:
            for sec in analysis.get('sections', []):
                if sec.get('heading') == '総論':
                    body = sec.get('body', '')
                    theme = clean(body.split('\n')[0]) if body else ''
                    break
            kikan = clean(analysis.get('period_definition', ''))
            # summary: 全sectionsのbodyを結合（KW検索用・38週フル対応）
            summary = ' '.join(
                clean(sec.get('body', ''))
                for sec in analysis.get('sections', [])
                if sec.get('body')
            )[:600]

        # 記事数
        articles = w.get('articles', [])
        articles_text = ' '.join(a.get('title', '') for a in articles)

        # カテゴリ集計
        cats = {c: sum(articles_text.count(kw) for kw in kws) for c, kws in KEYWORDS.items()}

        results.append({
            'week': label,
            'articles': w.get('article_count', len(articles)),
            'theme': theme,
            'kikan': kikan,
            'summary': summary,
            'categories': cats,
        })

    return results

# ── 記事データ抽出 ─────────────────────────────────────────
def extract_articles(data):
    results = []
    for w in data['weekly']:
        period = w.get('period', {})
        key = period.get('key', '')
        label = key.replace('_', ' 〜 ').replace('-', '/') if '_' in key else key

        for a in w.get('articles', []):
            url = a.get('url', '')
            title = clean(a.get('title', ''))
            if url and title and len(title) >= 4:
                results.append({'title': title[:120], 'url': url, 'week': label})
    return results

# ── アコーディオン共通 ──────────────────────────────────────
THEME_COLORS = ['#388E3C','#29B6F6','#AB47BC','#FF7043','#26A69A','#FFA726','#EC407A']
PHASE_ICONS  = ['🛡️','⚖️','🎯','🔥','💡','🌊']
PHASE_COLORS = [('#4CAF50','#E8F5E9'),('#F9A825','#FFFDE7'),('#E64A19','#FBE9E7'),('#1565C0','#E3F2FD')]

def sections_to_themes(sections, skip_headings=None):
    """sections[]からテーマカードリストを生成"""
    if skip_headings is None:
        skip_headings = {'総論','期間定義','🌐 Q1総括','🌐 Q総括','🔮 次の論点（Q2に向けて）',
                         '📊 月別変化（最重要）','🌐 3月総括','📊 Q1全体で見ると','🔧 実務示唆',
                         '🔎 この週の位置づけ','🔧 実務への示唆','🌐 総括'}
    themes = []
    for sec in sections:
        heading = sec.get('heading', '')
        if not heading or heading in skip_headings: continue
        if heading.startswith('🔎') or heading.startswith('🔮'): continue
        body = clean(sec.get('body', ''))[:100]
        title = re.sub(r'^[①②③④⑤⑥⑦⑧\d+\.\s]+', '', heading).strip().strip('「」')
        if len(title) > 3:
            themes.append({'title': title, 'body': body})
        if len(themes) >= 7: break
    return themes

def build_accordion_item(qid, is_open, label, subtitle, soron, kikan, phases, themes, wrap, color_primary):
    html  = '<div class="q-accordion" id="{}">\n'.format(qid)
    html += '  <div class="q-header" onclick="toggleQ(\'{}\')">\n'.format(qid)
    html += '    <div style="display:flex;align-items:center;gap:12px;flex:1;flex-wrap:wrap">\n'
    html += '      <span style="background:{};color:#fff;font-size:11px;font-weight:900;padding:4px 12px;border-radius:12px">{}</span>\n'.format(color_primary, H.escape(label))
    html += '      <span style="font-size:13px;font-weight:700;color:var(--tx)">{}</span>\n'.format(H.escape(subtitle))
    html += '    </div>\n'
    html += '    <span class="q-chevron" id="{}-chev">{}</span>\n'.format(qid, '▲' if is_open else '▼')
    html += '  </div>\n'
    html += '  <div class="q-body" id="{}-body" style="display:{}">\n'.format(qid, 'block' if is_open else 'none')

    # 総論 + 期間定義
    if soron or kikan:
        html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px;margin-bottom:16px">\n'
        if soron:
            html += '      <div style="font-size:10px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">📌 総論</div>\n'
            html += '      <div style="font-size:14px;font-weight:700;color:var(--tx);line-height:1.6;margin-bottom:{}px">{}</div>\n'.format(10 if kikan else 0, H.escape(soron))
        if kikan:
            html += '      <div style="background:rgba(255,255,255,0.7);padding:8px 12px;border-radius:8px;font-size:13px;margin-top:8px">💡 期間定義：<strong>{}</strong></div>\n'.format(H.escape(kikan))
        html += '    </div>\n'

    # 月別フェーズ（Q総括のみ）
    if phases:
        html += '    <div style="margin-bottom:16px">\n'
        html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">📊 月別フェーズ</div>\n'
        html += '      <div style="display:flex;gap:10px;flex-wrap:wrap">\n'
        for pi, ph in enumerate(phases[:4]):
            col, bg = PHASE_COLORS[pi % len(PHASE_COLORS)]
            html += '        <div style="background:#fff;border-radius:12px;padding:14px;border:1.5px solid {};flex:1;min-width:150px">\n'.format(bg)
            html += '          <div style="font-size:18px;margin-bottom:5px">{}</div>\n'.format(PHASE_ICONS[pi % len(PHASE_ICONS)])
            html += '          <div style="font-size:12px;font-weight:900;color:{};margin-bottom:4px">{}</div>\n'.format(col, H.escape(ph['name']))
            html += '          <div style="font-size:11px;color:var(--ts);line-height:1.6;margin-bottom:5px">{}</div>\n'.format('／'.join(H.escape(x) for x in ph.get('items', [])))
            html += '          <div style="background:{};padding:4px 9px;border-radius:8px;font-size:11px;font-weight:700;color:{}">KW：{}</div>\n'.format(bg, col, H.escape(ph.get('kw', '')))
            html += '        </div>\n'
        html += '      </div>\n    </div>\n'

    # テーマ別考察
    if themes:
        html += '    <div style="margin-bottom:16px">\n'
        html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">🔍 テーマ別考察</div>\n'
        html += '      <div style="display:flex;flex-direction:column;gap:8px">\n'
        for ti, th in enumerate(themes):
            col = THEME_COLORS[ti % len(THEME_COLORS)]
            num = '①②③④⑤⑥⑦'[ti] if ti < 7 else '•'
            html += '        <div style="background:#fff;border-radius:10px;padding:12px;border:1.5px solid #eee;border-left:3px solid {}">\n'.format(col)
            html += '          <div style="font-size:10px;font-weight:900;color:{};text-transform:uppercase;margin-bottom:4px">{} {}</div>\n'.format(col, num, H.escape(th['title']))
            html += '          <div style="font-size:12px;color:var(--ts);line-height:1.6">{}</div>\n'.format(H.escape(th['body']))
            html += '        </div>\n'
        html += '      </div>\n    </div>\n'

    # 締め
    if wrap:
        html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px">\n'
        html += '      <div style="font-size:13px;font-weight:700;color:var(--tx);line-height:1.6">{}</div>\n'.format(H.escape(wrap))
        html += '    </div>\n'

    html += '  </div>\n</div>\n'
    return html

def build_accordion_html(items, id_prefix, color_primary='var(--green)'):
    if not items:
        return '<div style="color:#888;padding:20px;font-size:14px">データがまだありません</div>'
    return '\n'.join(
        build_accordion_item(
            '{}-{}'.format(id_prefix, i), i == 0,
            q['label'], q['subtitle'], q['soron'], q['kikan'],
            q.get('phases', []), q.get('themes', []), q.get('wrap', ''),
            color_primary
        )
        for i, q in enumerate(items)
    )

# ── 四半期考察 ─────────────────────────────────────────────
def extract_quarters(data):
    results = []
    for q in data.get('quarterly', []):
        period = q.get('period', {})
        year = period.get('year', '')
        qnum = period.get('quarter', '')
        label = '{}年Q{}'.format(year, qnum)

        soron_lines = clean(q.get('summary', '')).split('\n')
        soron = soron_lines[0] if soron_lines else ''
        kikan = clean(q.get('period_definition', '') or '')

        sections = q.get('sections', [])
        themes = sections_to_themes(sections)

        # 月別フェーズ
        phases = []
        for sec in sections:
            h = sec.get('heading', '')
            m = re.match(r'(\d+)月：(\S+フェーズ)', h)
            if m:
                body = sec.get('body', '')
                items = [line.strip() for line in body.split('\n') if line.strip() and not line.startswith('👉')][:4]
                kw_m = re.search(r'キーワード[：:]\s*(.+)', body)
                phases.append({
                    'name': m.group(2),
                    'items': items,
                    'kw': kw_m.group(1).strip() if kw_m else '',
                })

        results.append({
            'label': label, 'subtitle': kikan or label + 'の考察',
            'soron': soron, 'kikan': kikan,
            'phases': phases, 'themes': themes, 'wrap': ''
        })
    return results

# ── 月次考察 ──────────────────────────────────────────────
def extract_monthly_reviews(data):
    results = []
    for m in data.get('monthly', []):
        period = m.get('period', {})
        year = period.get('year', '')
        month = period.get('month', '')
        label = '{}年{}月'.format(year, month)

        soron_lines = clean(m.get('summary', '')).split('\n')
        soron = soron_lines[0] if soron_lines else ''
        kikan = clean(m.get('period_definition', '') or '')

        sections = m.get('sections', [])
        themes = sections_to_themes(sections)

        results.append({
            'label': label, 'subtitle': kikan or label + 'の考察',
            'soron': soron, 'kikan': kikan,
            'phases': [], 'themes': themes, 'wrap': ''
        })
    # 年月の数値順でソート（例: 2026年3月 > 2025年10月）
    def month_key(r):
        m = re.match(r'(\d{4})年(\d+)月', r['label'])
        return (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    results.sort(key=month_key, reverse=True)
    seen = set()
    deduped = []
    for r in results:
        if r['label'] not in seen:
            seen.add(r['label'])
            deduped.append(r)
    return deduped

# ── 年次考察 ──────────────────────────────────────────────
def extract_annual_reviews(data):
    results = []
    for a in data.get('annual', []):
        period = a.get('period', {})
        year = period.get('year', '')
        label = '{}年 年次考察'.format(year)

        soron = clean(a.get('summary', ''))
        kikan = clean(a.get('period_definition', '') or '')

        sections = a.get('sections', [])
        themes = sections_to_themes(sections, skip_headings={
            '総論','期間定義','🌐 総括','🔮 次の論点'
        })

        # 年次の締め（7番目テーマのbody）
        wrap = ''
        for sec in sections:
            if '一本の思想' in sec.get('heading', '') or '2025年を貫く' in sec.get('heading', ''):
                body = sec.get('body', '')
                wrap = clean(body.split('\n')[0])[:120] if body else ''
                break

        results.append({
            'label': label, 'subtitle': soron[:60] if soron else label + 'の考察',
            'soron': soron, 'kikan': kikan,
            'phases': [], 'themes': themes, 'wrap': wrap
        })
    results.sort(key=lambda x: x['label'], reverse=True)
    return results

# ── メイン ────────────────────────────────────────────────
def main():
    json_files = glob.glob('data/*.json')
    if not json_files:
        print("❌ data/ フォルダに .json ファイルが見つかりません"); return

    json_path = json_files[0]
    print("📄 読み込み: {}".format(json_path))

    data            = load_json(json_path)
    weeks_data      = extract_weeks(data)
    articles_data   = extract_articles(data)
    quarters        = extract_quarters(data)
    monthly_reviews = extract_monthly_reviews(data)
    annual_reviews  = extract_annual_reviews(data)

    themed = sum(1 for w in weeks_data if w['theme'])
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
