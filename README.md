# Z世代 Signal Atlas

Z世代・若年層の週次記事データを可視化するダッシュボード。

## 🔄 毎週の更新方法

**1. docxファイルを差し替える**

`data/` フォルダにある `.docx` ファイルを新しいものに差し替えてGitHubにpushするだけ。

```
data/
  └── zgene.docx  ← これを新しいファイルに差し替える
```

**2. pushしたら自動更新**

GitHub Actionsが自動で以下を実行する：
1. docxを解析してデータ抽出
2. HTMLダッシュボードを生成
3. GitHub Pagesにデプロイ

通常1〜2分で https://yutate.github.io/genz/ に反映される。

## 📁 ファイル構成

```
genz/
  ├── data/
  │   └── zgene.docx          ← 毎週ここを更新するだけ
  ├── scripts/
  │   ├── build.py            ← データ変換スクリプト
  │   └── template.html       ← ダッシュボードのHTMLテンプレート
  └── .github/
      └── workflows/
          └── update.yml      ← GitHub Actions設定
```

## 🛠 ローカルで動かす場合（Mac）

```bash
# 依存ライブラリのインストール（初回のみ）
pip3 install python-docx

# ビルド実行
python3 scripts/build.py

# dist/index.html をブラウザで開く
open dist/index.html
```

## ⚙️ GitHub Pages の設定

初回セットアップ時：
1. リポジトリの Settings → Pages
2. Source を `gh-pages` ブランチに設定
