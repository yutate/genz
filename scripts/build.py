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

# ── 週データ抽出 ───────────────────────────────────────────
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
        for pat in [r'週次精読版\n\n「(.+?)」', r'テーマ\n+###\s*(.{15,100})']:
            m = re.search(pat, sec)
            if m: return re.sub(r'\*\*','',m.group(1)).strip()
        for marker in ['今週の結論','今週の総括','総括（最終）']:
            m = re.search(marker+r'\n+([^\n]{15,100})', sec)
            if m:
                t = re.sub(r'\*\*','',m.group(1)).strip()
                if len(t)>15: return t
        m = re.search(r'👉\s*「?(.{15,80})」?', sec)
        if m: return re.sub(r'\*\*','',m.group(1)).strip()
        return None

    wks = list(re.finditer(r'✅ Z世代・若年層関連記事まとめ（(.+?)）', text))
    results = []
    for i,w in enumerate(wks):
        s = w.end(); e = wks[i+1].start() if i+1<len(wks) else len(text)
        sec = text[s:e]
        results.append({
            'week': w.group(1),
            'articles': len(re.findall(r'https?://', sec)),
            'theme': get_theme(sec),
            'categories': {c: sum(sec.count(kw) for kw in kws) for c,kws in KEYWORDS.items()},
        })
    return results

# ── 記事データ抽出 ─────────────────────────────────────────
def extract_articles(text):
    wks = list(re.finditer(r'✅ Z世代・若年層関連記事まとめ（(.+?)）', text))
    results = []
    for i,w in enumerate(wks):
        s = w.end(); e = wks[i+1].start() if i+1<len(wks) else len(text)
        sec = text[s:e]; week_name = w.group(1); seen = set()
        for line in sec.split('\n'):
            line = line.strip()
            urls = re.findall(r'https?://[^\s\)\]]+', line)
            if not urls: continue
            url = urls[0].rstrip(')')
            if url in seen or not url.startswith('http'): continue
            seen.add(url)
            t = re.sub(r'\[\[.+','',line)
            t = re.sub(r'^[・\-\s]+','',t)
            t = re.sub(r'\{\.underline\}|\[|\]|\*\*','',t)
            t = re.sub(r'https?://\S+','',t)
            t = re.sub(r'\s*-\s*$','',t.strip().rstrip('\\')).strip()
            if len(t)>=8 and not t.startswith('```'):
                results.append({'title':t[:120],'url':url,'week':week_name})
    return results

# ── Q総括 抽出 & アコーディオンHTML生成 ──────────────────────
PHASE_ICONS  = ['🛡️','⚖️','🎯','🔥','💡','🌊']
PHASE_COLORS = [('#4CAF50','#E8F5E9'),('#F9A825','#FFFDE7'),('#E64A19','#FBE9E7'),('#1565C0','#E3F2FD')]
THEME_COLORS = ['#388E3C','#29B6F6','#AB47BC','#FF7043','#26A69A','#FFA726','#EC407A']

def extract_quarters(text):
    q_matches = list(re.finditer(r'(\d{4})年Q(\d+)\s*総合考察', text))
    if not q_matches: return []
    fw = re.search(r'✅ Z世代・若年層関連記事まとめ', text)
    end_q = fw.start() if fw else len(text)

    results = []
    for i,qm in enumerate(q_matches):
        year,q_num = qm.group(1),qm.group(2)
        s = qm.start()
        e = q_matches[i+1].start() if i+1<len(q_matches) else end_q
        sec = text[s:e].strip()

        soron_m = re.search(r'Z世代は「(.+?)」から\n?「(.+?)」へ移行した', sec)
        soron = soron_m.group(0).replace('\n','') if soron_m else ''

        ol_m = re.search(r'「([^」]{10,60})」が標準になった', sec)
        oneliner = '「{}」が標準になった四半期'.format(ol_m.group(1)) if ol_m else ''

        phases = []
        for m in re.finditer(r'(\d+)月：(\S+フェーズ)\n(.+?)キーワード[：:]\s*\*\*?([^\n*]+)\*\*?', sec, re.DOTALL):
            items = re.findall(r'[-・]\s*(.+)', m.group(3).strip())
            phases.append({'month':m.group(1)+'月','name':m.group(2),'items':[x.strip() for x in items[:4]],'kw':m.group(4).strip()})

        themes = []
        for tm in list(re.finditer(r'[①②③④⑤⑥⑦⑧⑨⑩]\s*「?(.+?)」?\n+(.+?)(?=[①②③④⑤⑥⑦⑧⑨⑩]|🌐|$)', sec, re.DOTALL))[:7]:
            title = tm.group(1).strip().strip('「」')
            body = re.sub(r'キー記事.+','',tm.group(2),flags=re.DOTALL)
            body = ' '.join(re.sub(r'\*\*|https?://\S+|[-・]\s*\n','',body).split())[:120]
            if len(title)>3: themes.append({'title':title,'body':body})

        wrap_m = re.search(r'Z世代は「拡張社会」を終わらせ[、,]\s*\n?「(.+?)」を作り始めた', sec)
        wrap = wrap_m.group(0).replace('\n','') if wrap_m else ''

        results.append({'year':year,'q_num':q_num,'label':'{}年Q{}'.format(year,q_num),
                        'soron':soron,'oneliner':oneliner,'phases':phases,'themes':themes,'wrap':wrap})
    return results

def build_q_accordion(quarters):
    if not quarters:
        return '<div style="color:#888;padding:20px;font-size:14px">Q総括データがまだありません</div>'
    parts = []
    for i,q in enumerate(quarters):
        qid = 'q-{}'.format(i)
        is_open = (i==0)
        label = H.escape(q['label'])
        ol = H.escape(q['oneliner']) if q['oneliner'] else label+'の総括'
        soron = H.escape(q['soron'])

        # ヘッダー
        html = '<div class="q-accordion" id="{}">\n'.format(qid)
        html += '  <div class="q-header" onclick="toggleQ(\'{}\')">\n'.format(qid)
        html += '    <div style="display:flex;align-items:center;gap:12px;flex:1;flex-wrap:wrap">\n'
        html += '      <span style="background:var(--green);color:#fff;font-size:11px;font-weight:900;padding:4px 12px;border-radius:12px">{}</span>\n'.format(label)
        html += '      <span style="font-size:13px;font-weight:700;color:var(--tx)">{}</span>\n'.format(ol)
        html += '    </div>\n'
        html += '    <span class="q-chevron" id="{}-chev">{}</span>\n'.format(qid, '▲' if is_open else '▼')
        html += '  </div>\n'
        html += '  <div class="q-body" id="{}-body" style="display:{}">\n'.format(qid, 'block' if is_open else 'none')

        # 総論
        if soron:
            ol_block = '<div style="margin-top:8px;background:rgba(255,255,255,0.7);padding:8px 12px;border-radius:8px;font-size:13px">💡 一言：<strong>{}</strong></div>'.format(H.escape(q['oneliner'])) if q['oneliner'] else ''
            html += '    <div style="background:linear-gradient(135deg,#E8F5E9,#FFFDE7);border-radius:12px;padding:14px 18px;margin-bottom:16px">\n'
            html += '      <div style="font-size:10px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:6px">📌 総論</div>\n'
            html += '      <div style="font-size:14px;font-weight:700;color:var(--tx);line-height:1.6">{}</div>\n'.format(soron)
            html += '      {}\n'.format(ol_block)
            html += '    </div>\n'

        # 月別フェーズ
        if q['phases']:
            html += '    <div style="margin-bottom:16px">\n'
            html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">📊 月別フェーズ</div>\n'
            html += '      <div style="display:flex;gap:10px;flex-wrap:wrap">\n'
            for pi,ph in enumerate(q['phases'][:4]):
                col,bg = PHASE_COLORS[pi%len(PHASE_COLORS)]
                icon = PHASE_ICONS[pi%len(PHASE_ICONS)]
                items_str = '／'.join(H.escape(x) for x in ph['items'])
                html += '        <div style="background:#fff;border-radius:12px;padding:14px;border:1.5px solid {};flex:1;min-width:150px">\n'.format(bg)
                html += '          <div style="font-size:18px;margin-bottom:5px">{}</div>\n'.format(icon)
                html += '          <div style="font-size:12px;font-weight:900;color:{};margin-bottom:4px">{}</div>\n'.format(col,H.escape(ph['name']))
                html += '          <div style="font-size:11px;color:var(--ts);line-height:1.6;margin-bottom:5px">{}</div>\n'.format(items_str)
                html += '          <div style="background:{};padding:4px 9px;border-radius:8px;font-size:11px;font-weight:700;color:{}">KW：{}</div>\n'.format(bg,col,H.escape(ph['kw']))
                html += '        </div>\n'
            html += '      </div>\n    </div>\n'

        # テーマ別考察
        if q['themes']:
            html += '    <div style="margin-bottom:16px">\n'
            html += '      <div style="font-size:11px;font-weight:900;color:var(--ts);letter-spacing:.1em;text-transform:uppercase;margin-bottom:10px">🔍 テーマ別考察</div>\n'
            html += '      <div style="display:flex;flex-direction:column;gap:8px">\n'
            for ti,th in enumerate(q['themes']):
                col = THEME_COLORS[ti%len(THEME_COLORS)]
                num = '①②③④⑤⑥⑦'[ti]
                html += '        <div style="background:#fff;border-radius:10px;padding:12px;border:1.5px solid #eee;border-left:3px solid {}">\n'.format(col)
                html += '          <div style="font-size:10px;font-weight:900;color:{};text-transform:uppercase;margin-bottom:4px">{} {}</div>\n'.format(col,num,H.escape(th['title']))
                html += '          <div style="font-size:12px;color:var(--ts);line-height:1.6">{}</div>\n'.format(H.escape(th['body']))
                html += '        </div>\n'
            html += '      </div>\n    </div>\n'

        # 締め
        if q['wrap']:
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

    text         = docx_to_text(docx_path)
    weeks_data   = extract_weeks(text)
    articles_data= extract_articles(text)
    quarters     = extract_quarters(text)

    themed = sum(1 for w in weeks_data if w['theme'])
    print("   テキスト: {:,} 文字".format(len(text)))
    print("   週数: {}  考察付き: {}  記事: {}  Q総括: {}件".format(
        len(weeks_data), themed, len(articles_data), len(quarters)))

    data_js  = 'const RAW='      + json.dumps(weeks_data,     ensure_ascii=False, separators=(',',':')) + ';\n'
    data_js += 'const ARTICLES=' + json.dumps(articles_data,  ensure_ascii=False, separators=(',',':')) + ';'

    tpl_path = os.path.join(os.path.dirname(__file__), 'template.html')
    with open(tpl_path, encoding='utf-8') as f:
        html = f.read()

    html = html.replace('// DATA_PLACEHOLDER',             data_js)
    html = html.replace('<!-- Q_ACCORDION_PLACEHOLDER -->', build_q_accordion(quarters))
    html = html.replace('<!-- Q_COUNT_PLACEHOLDER -->',     str(len(quarters)))
    html = html.replace('<!-- WEEK_COUNT_PLACEHOLDER -->',  str(len(weeks_data)))
    html = html.replace('<!-- ARTICLE_COUNT_PLACEHOLDER -->','{:,}'.format(len(articles_data)))

    os.makedirs('dist', exist_ok=True)
    out = 'dist/index.html'
    with open(out, 'w', encoding='utf-8') as f:
        f.write(html)
    print("✅ 生成完了: {} ({}KB)".format(out, os.path.getsize(out)//1024))

if __name__ == '__main__':
    main()
