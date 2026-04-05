#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Z世代 Signal Atlas - Build Script
data/zgene_v2.json -> dist/index.html を自動生成する

JSONスキーマ（新):
  トップレベル: list
  type: weekly / monthly / quarterly / annual で判定
  weekly:
    period.start / period.end
    articles[]: {title, url, ...}
    essay:
      summary, period_definition, keywords[], sections[], structure
  monthly / quarterly / annual:
    period, summary, period_definition, sections[]
"""

import os, re, json, glob, html as H
from collections import Counter

def load_json(path):
    with open(path, encoding='utf-8') as f:
        return json.load(f)

def clean(s):
    if not s: return ''
    return re.sub(r'\s+', ' ', re.sub(r'\*\*|\\n', '', str(s))).strip()

def period_label(period):
    """period.start/end -> 表示ラベル"""
    s = period.get('start', '')
    e = period.get('end', '')
    if s and e:
        # YYYY-MM-DD -> YYYY/MM/DD
        return s.replace('-', '/') + ' 〜 ' + e.replace('-', '/')
    if s:
        return s.replace('-', '/')
    return ''

def period_ym(period):
    """period.start -> YYYY/MM"""
    s = period.get('start', '')
    m = re.match(r'(\d{4})-(\d{2})', s)
    return '{}/{}'.format(m.group(1), m.group(2)) if m else ''

# ── 週次データ抽出 ─────────────────────────────────────────
def extract_weeks(entries):
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
    warnings = []
    weekly = [e for e in entries if e.get('type') == 'weekly']

    for w in weekly:
        period = w.get('period', {})
        label = period_label(period)
        essay = w.get('essay') or {}
        articles = w.get('articles') or []

        # articlesが空の場合はwarning
        if len(articles) == 0:
            warnings.append('⚠️  articles 0件: {}'.format(label))

        # テーマ（summary の1行目）
        summary_full = clean(essay.get('summary', ''))
        theme = summary_full.split('\n')[0] if summary_full else ''

        # 期間定義
        kikan = clean(essay.get('period_definition', '') or '')

        # summary全文（KW検索用）
        summary = summary_full
        # sectionsのbodyも追加
        for sec in essay.get('sections', []):
            body = clean(sec.get('body', ''))
            if body:
                summary += ' ' + body
        summary = summary[:600]

        # keywords（配列）
        keywords = essay.get('keywords', [])

        # カテゴリ集計（記事タイトルから）
        articles_text = ' '.join(a.get('title', '') for a in articles)
        cats = {c: sum(articles_text.count(kw) for kw in kws) for c, kws in KEYWORDS.items()}

        results.append({
            'week':     label,
            'articles': len(articles),
            'theme':    theme,
            'kikan':    kikan,
            'summary':  summary,
            'keywords': keywords,
            'categories': cats,
        })

    return results, warnings

# ── 記事データ抽出 ─────────────────────────────────────────
def extract_articles(entries):
    results = []
    weekly = [e for e in entries if e.get('type') == 'weekly']
    for w in weekly:
        period = w.get('period', {})
        label = period_label(period)
        for a in (w.get('articles') or []):
            url = a.get('url', '')
            title = clean(a.get('title', ''))
            if url and title and len(title) >= 4:
                results.append({'title': title[:120], 'url': url, 'week': label})
    return results

# ── アコーディオン共通 ──────────────────────────────────────
THEME_COLORS = ['#388E3C','#29B6F6','#AB47BC','#FF7043','#26A69A','#FFA726','#EC407A']
PHASE_ICONS  = ['🛡️','⚖️','🎯','🔥','💡','🌊']
PHASE_COLORS = [('#4CAF50','#E8F5E9'),('#F9A825','#FFFDE7'),('#E64A19','#FBE9E7'),('#1565C0','#E3F2FD')]

def sections_to_themes(sections, skip=None):
    if skip is None:
        skip = {'総論','期間定義','🌐 Q1総括','🌐 Q総括','🔮 次の論点',
                '📊 月別変化（最重要）','🌐 総括','🔧 実務示唆','🔎 この週の位置づけ',
                '🔧 実務への示唆','📊 Q1全体で見ると'}
    themes = []
    for sec in sections:
        h = sec.get('heading', '')
        if not h or h in skip or h.startswith('🔎') or h.startswith('🔮'): continue
        title = re.sub(r'^[①②③④⑤⑥⑦⑧\d+\.\s]+', '', h).strip().strip('「」')
        body = clean(sec.get('body', ''))[:100]
        if len(title) > 3:
            themes.append({'title': title, 'body': body})
        if len(themes) >= 7: break
    return themes

def build_accordion_item(qid, is_open, label, subtitle, soron, kikan, phases, themes, wrap, color):
    e = H.escape
    html  = '<div class="q-accordion" id="{}">\n'.format(qid)
    html += '  <div class="q-header" onclick="toggleQ(\'{}\')">\n'.format(qid)
    html += '    <div style="display:flex;align-items:center;gap:12px;flex:1;flex-wrap:wrap">\n'
    html += '      <span style="background:{};color:#fff;font-size:11px;font-weight:900;padding:4px 12px;border-radius:12px">{}</span>\n'.format(color, e(label))
    html += '      <span style="font-size:13px;font-weight:700;color:var(--tx)">{}</span>\n'.format(e(subtitle))
    html += '    </div>\n'
    html += '    <span class="q-chevron" id="{}-chev">{}</span>\n'.format(qid, '▲' if is_open else '▼')
    html += '  </div>\n'
    html += '  <div class="q-body" id="{}-body" style="display:{}">\n'.format(qid, 'block' if is_open else 'none')

    if soron or kikan:
        html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px;margin-bottom:16px">\n'
        if soron:
            html += '      <div style="font-size:10px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">📌 総論</div>\n'
            html += '      <div style="font-size:14px;font-weight:700;color:var(--tx);line-height:1.6;margin-bottom:{}px">{}</div>\n'.format(10 if kikan else 0, e(soron))
        if kikan:
            html += '      <div style="background:rgba(255,255,255,0.7);padding:8px 12px;border-radius:8px;font-size:13px;margin-top:8px">💡 期間定義：<strong>{}</strong></div>\n'.format(e(kikan))
        html += '    </div>\n'

    if phases:
        html += '    <div style="margin-bottom:16px">\n'
        html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">📊 月別フェーズ</div>\n'
        html += '      <div style="display:flex;gap:10px;flex-wrap:wrap">\n'
        for pi, ph in enumerate(phases[:4]):
            col, bg = PHASE_COLORS[pi % len(PHASE_COLORS)]
            html += '        <div style="background:#fff;border-radius:12px;padding:14px;border:1.5px solid {};flex:1;min-width:150px">\n'.format(bg)
            html += '          <div style="font-size:18px;margin-bottom:5px">{}</div>\n'.format(PHASE_ICONS[pi % len(PHASE_ICONS)])
            html += '          <div style="font-size:12px;font-weight:900;color:{};margin-bottom:4px">{}</div>\n'.format(col, e(ph['name']))
            html += '          <div style="font-size:11px;color:var(--ts);line-height:1.6;margin-bottom:5px">{}</div>\n'.format('／'.join(e(x) for x in ph.get('items', [])))
            html += '          <div style="background:{};padding:4px 9px;border-radius:8px;font-size:11px;font-weight:700;color:{}">KW：{}</div>\n'.format(bg, col, e(ph.get('kw', '')))
            html += '        </div>\n'
        html += '      </div>\n    </div>\n'

    if themes:
        html += '    <div style="margin-bottom:16px">\n'
        html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">🔍 テーマ別考察</div>\n'
        html += '      <div style="display:flex;flex-direction:column;gap:8px">\n'
        for ti, th in enumerate(themes):
            col = THEME_COLORS[ti % len(THEME_COLORS)]
            num = '①②③④⑤⑥⑦'[ti] if ti < 7 else '•'
            html += '        <div style="background:#fff;border-radius:10px;padding:12px;border:1.5px solid #eee;border-left:3px solid {}">\n'.format(col)
            html += '          <div style="font-size:10px;font-weight:900;color:{};text-transform:uppercase;margin-bottom:4px">{} {}</div>\n'.format(col, num, e(th['title']))
            html += '          <div style="font-size:12px;color:var(--ts);line-height:1.6">{}</div>\n'.format(e(th['body']))
            html += '        </div>\n'
        html += '      </div>\n    </div>\n'

    if wrap:
        html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px">\n'
        html += '      <div style="font-size:13px;font-weight:700;color:var(--tx);line-height:1.6">{}</div>\n'.format(e(wrap))
        html += '    </div>\n'

    html += '  </div>\n</div>\n'
    return html

def build_accordion_html(items, id_prefix, color='var(--green)'):
    if not items:
        return '<div style="color:#888;padding:20px;font-size:14px">データがまだありません</div>'
    return '\n'.join(
        build_accordion_item(
            '{}-{}'.format(id_prefix, i), i == 0,
            q['label'], q['subtitle'], q['soron'], q['kikan'],
            q.get('phases', []), q.get('themes', []), q.get('wrap', ''), color
        )
        for i, q in enumerate(items)
    )

# ── 四半期・月次・年次 抽出 ───────────────────────────────
def extract_summary_entries(entries, entry_type, id_prefix):
    results = []
    seen = set()
    targets = [e for e in entries if e.get('type') == entry_type]

    for e in targets:
        period = e.get('period', {})
        # ラベル生成
        if entry_type == 'quarterly':
            # period.start から年とQを判定
            start = period.get('start', '')
            m = re.match(r'(\d{4})-(\d{2})', start)
            if m:
                month = int(m.group(2))
                q_num = (month - 1) // 3 + 1
                label = '{}年Q{}'.format(m.group(1), q_num)
            else:
                label = e.get('title', '四半期考察')
        elif entry_type == 'monthly':
            start = period.get('start', '')
            m = re.match(r'(\d{4})-(\d{2})', start)
            label = '{}年{}月'.format(m.group(1), int(m.group(2))) if m else e.get('title', '月次考察')
        elif entry_type == 'annual':
            start = period.get('start', '')
            m = re.match(r'(\d{4})', start)
            label = '{}年 年次考察'.format(m.group(1)) if m else e.get('title', '年次考察')
        else:
            label = str(period)

        if label in seen: continue
        seen.add(label)

        # essayから取得
        essay = e.get('essay') or {}
        summary_raw = clean(essay.get('summary', ''))
        soron = summary_raw.split('\n')[0] if summary_raw else ''
        kikan = clean(essay.get('period_definition', '') or '')
        sections = essay.get('sections', [])
        themes = sections_to_themes(sections)

        # 月別フェーズ（quarterly のみ）
        phases = []
        if entry_type == 'quarterly':
            for sec in sections:
                h = sec.get('heading', '')
                m2 = re.match(r'(\d+)月：(\S+フェーズ)', h)
                if m2:
                    body = sec.get('body', '')
                    items = [l.strip() for l in body.split('\n') if l.strip() and not l.startswith('👉')][:4]
                    kw_m = re.search(r'キーワード[：:]\s*(.+)', body)
                    phases.append({'name': m2.group(2), 'items': items, 'kw': kw_m.group(1).strip() if kw_m else ''})

        results.append({
            'label': label,
            'subtitle': kikan or label + 'の考察',
            'soron': soron, 'kikan': kikan,
            'phases': phases, 'themes': themes, 'wrap': ''
        })

    # 年月順ソート
    def sort_key(r):
        m = re.match(r'(\d{4})年(?:Q(\d+)|(\d+)月)?', r['label'])
        if m:
            yr = int(m.group(1))
            q_or_m = int(m.group(2) or m.group(3) or 0)
            return (yr, q_or_m)
        return (0, 0)

    results.sort(key=sort_key, reverse=True)
    return results

# ── グローバルキーワードリスト生成 ──────────────────────────
def build_global_kws(entries):
    """全entryのessay.keywordsのユニーク一覧を出現頻度順で返す"""
    kw_counter = Counter()
    for e in entries:
        kws = e.get('essay', {}).get('keywords', [])
        kw_counter.update(kws)
    # 出現頻度順（全KWを返す）
    return [kw for kw, _ in kw_counter.most_common()]

# ── メイン ────────────────────────────────────────────────
def main():
    # zgene.json を読み込む
    json_files = glob.glob('data/zgene.json')
    if not json_files:
        print("❌ data/zgene.json が見つかりません"); return

    json_path = json_files[0]
    print("📄 読み込み: {}".format(json_path))

    entries = load_json(json_path)

    weeks_data, warnings    = extract_weeks(entries)
    articles_data           = extract_articles(entries)
    quarters                = extract_summary_entries(entries, 'quarterly', 'q')
    monthly_reviews         = extract_summary_entries(entries, 'monthly',   'm')
    annual_reviews          = extract_summary_entries(entries, 'annual',    'a')
    global_kws              = build_global_kws(entries)

    themed = sum(1 for w in weeks_data if w['theme'])
    print("   週数: {}  考察付き: {}  記事: {}  四半期: {}件  月次: {}件  年次: {}件".format(
        len(weeks_data), themed, len(articles_data),
        len(quarters), len(monthly_reviews), len(annual_reviews)))
    print("   グローバルKW: {}件".format(len(global_kws)))

    if warnings:
        for w in warnings:
            print("   " + w)

    data_js  = 'const RAW='      + json.dumps(weeks_data,    ensure_ascii=False, separators=(',', ':')) + ';\n'
    data_js += 'const ARTICLES=' + json.dumps(articles_data, ensure_ascii=False, separators=(',', ':')) + ';\n'
    data_js += 'const GLOBAL_KWS=' + json.dumps(global_kws, ensure_ascii=False, separators=(',', ':')) + ';'

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
