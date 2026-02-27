# ctxforge

AI CLI 向けのシンプルなコンテキスト管理ツール。

profile を定義し、重要ファイルを選び、プロジェクト文脈付きで AI CLI を起動します。

## インストール

```bash
pip install ctxforge
```

Python 3.11 以上が必要です。あわせて少なくとも 1 つの AI CLI（例: [Claude Code](https://docs.anthropic.com/en/docs/claude-code)）をインストールしてください。

## クイックスタート（2 ステップ）

```bash
cd your-project/

# 1) 初期化
ctxforge init

# 2) 実行
ctxforge run
```

`ctxforge init` はプロジェクト設定と最初の profile を作成します。

`ctxforge run` はその profile を読み込み、選択した文脈で対話型 AI CLI セッションを開始します。

## よく使うコマンド

| コマンド | 説明 |
|---------|------|
| `ctxforge init [PATH]` | プロジェクトの ctxforge 設定を初期化 |
| `ctxforge run [PROFILE]` | 指定 profile で AI CLI セッションを開始 |
| `ctxforge profile create NAME` | 新しい profile を作成 |
| `ctxforge profile list` | profile 一覧を表示 |
| `ctxforge profile show NAME` | profile 詳細を表示 |
| `ctxforge clean [PATH]` | ctxforge 設定を削除 |

## ミニマム例

```bash
ctxforge profile create reviewer --desc "Code review" --prompt "You are a code reviewer..."
ctxforge run reviewer
```

## 内蔵スラッシュコマンド（Claude Code のみ）

Claude Code をアクティブ CLI として使用する場合、ctxforge は `/project:ctx-*` スラッシュコマンドを生成します：

| コマンド | 説明 |
|---------|------|
| `/project:ctx-profile` | 現在の profile 設定を表示 |
| `/project:ctx-files` | key files の一覧とサイズを表示 |
| `/project:ctx-update` | AI が key files の更新を提案 |
| `/project:ctx-compress` | AI が冗長な key files を圧縮 |

これらのコマンドは他の CLI（例: Codex）では利用できません。

## メモ

ctxforge のプロジェクト設定と profile 設定は `.ctxforge/` に保存されます。
必要に応じて手動編集できます。
手動で変更した後は、`ctxforge run` を再実行して最新の文脈を反映してください。

## ライセンス
MIT
