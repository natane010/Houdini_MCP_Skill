# Codex と Claude Code のプロジェクト連携

このブリッジはローカル stdio MCP サーバーです。Codex と Claude Code は別々のプロジェクト設定を読み込みます。共通の起動コマンドを使えますが、設定ファイルとスキルの配置先はそれぞれ異なります。

## 前提

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
```

`hython` は同じ Houdini インストールに付属する実行ファイルを指定します。例は Houdini 22.0.368 の Windows パスです。実際のインストール場所に置き換えてください。

## 設定を計画する

プロジェクト設定とスキル配置の dry run はリポジトリルートから行えます。

```powershell
.venv\Scripts\python.exe scripts\setup_clients.py `
  --project-dir "E:\Projects\HoudiniMCP" `
  --client both `
  --backend batch `
  --hython "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe"
```

`--apply` を付けない限り、このコマンドは JSON の計画を表示するだけです。適用すると、選択したプロジェクト内に Codex 用 `.codex/config.toml` と `.agents/skills/`、Claude Code 用 `.mcp.json` と `.claude/skills/` を作成します。ユーザー全体の MCP 設定やホームディレクトリのスキルは変更しません。適用は明示的に実行してください。

Codex だけ、または Claude Code だけに行う場合は `--client codex` または `--client claude` を指定します。スクリプトは既存設定を読み、同名の `houdini` サーバーやスキルが異なる内容なら競合として拒否します。設定・スキルの配置先には通常のディレクトリを使ってください。シンボリックリンクと Windows のジャンクションは拒否します。同じ設定は再実行できます。すべての競合確認を先に行いますが、適用中の複数ファイル更新は一括トランザクションではありません。

設定を適用する場合の実行例:

```powershell
.venv\Scripts\python.exe scripts\setup_clients.py `
  --project-dir "E:\Projects\HoudiniMCP" `
  --client both `
  --backend batch `
  --hython "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe" `
  --allow-python `
  --apply
```

`--allow-python` を指定すると、ツール一覧に `execute_python` が追加され、Houdini の権限で Python を実行できます。Python 実行が必要なワークフローで指定してください。MCP サーバーの仮想環境にはプロジェクトを editable install しておきます。

### GUI バックエンド

Houdini GUI に接続する場合は `--backend gui` を指定します。既定ポートは `18811` です。先に Houdini の Python Shell で bootstrap を起動します。

```python
import runpy
gui = runpy.run_path(r"E:\Projects\HoudiniMCP\scripts\start_gui_loopback.py")
houdini_mcp_gui = gui["start_server"]()
```

既定ではユーザーのホームにある `.houdini-mcp/gui-18811.token` が初回に作成されます。MCP も同じファイルを読み取ります。複数の Houdini を開く場合は、Houdini 側の `start_server(port=18812)` と MCP 側の `--port 18812` を揃えます。明示的にトークンを置く場合は Houdini 側の `token_file` と MCP 側の `--gui-token-file` に同じ絶対パスを指定してください。ユーザー専用のフォルダーを利用します。起動時に接続できた場合、MCP のログに `hip_file`、`unsaved_changes`、`session_id` が出ます。同じ項目は `reconnect` または `connection_status` でも確認できます。Houdini 内で停止する場合は `houdini_mcp_gui.stop()` を実行します。

設定前のプロジェクトでは、導入コマンドの `--backend batch --hython ...` を `--backend gui` に置き換えます。既存設定を切り替える場合は、クライアント設定の `houdini` エントリで `--backend` を `gui` にし、`--hython` と実行ファイルのパスを削除してからクライアントを再接続します。`--port` と `--gui-token-file` は `setup_clients.py` にも渡せます。

旧 bootstrap を読み込んだ Houdini は再起動してから新しい手順を使います。GUI で `execute_python` を使う場合に限り、Houdini 側の `start_server(allow_python=True)` と MCP 側の `--allow-python` を両方指定します。

## Codex 設定

Codex CLI、Codex IDE 拡張、ChatGPT デスクトップアプリは Codex の MCP 設定を共有します。プロジェクトスコープの MCP サーバーは、信頼済みプロジェクトの `.codex/config.toml` に置きます。`setup_clients.py --client codex --apply` が作成する形は次のとおりです。

```toml
[mcp_servers.houdini]
command = "E:/Projects/HoudiniMCP/.venv/Scripts/python.exe"
args = ["-m", "houdini_mcp.server", "--backend", "batch", "--hython", "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe"]
```

`--allow-python` を選んだ場合、`args` の末尾に `"--allow-python"` が追加されます。Codex の設定画面から追加する場合も、プロジェクトスコープで登録してください。接続後は Codex の `/mcp` で状態を確認します。

## Claude Code 設定

Claude Code はプロジェクトルートの `.mcp.json` を使います。プロジェクト MCP は初回利用時にワークスペースの信頼とサーバー利用の確認が必要です。`setup_clients.py --client claude --apply` が作成する形は次のとおりです。

```json
{
  "mcpServers": {
    "houdini": {
      "type": "stdio",
      "command": "E:/Projects/HoudiniMCP/.venv/Scripts/python.exe",
      "args": [
        "-m", "houdini_mcp.server",
        "--backend", "batch",
        "--hython", "C:/Program Files/Side Effects Software/Houdini 22.0.368/bin/hython.exe"
      ]
    }
  }
}
```

`--allow-python` を選ぶと、同じく `args` に追加されます。Claude Code 内では `/mcp` で状態を確認し、必要ならサーバーを承認します。MCP ツール名の表示にはクライアント固有の接頭辞が付くことがあります。スキルや手順では、接頭辞ではなくサーバーが公開するツール名（例 `node_inspect`）を使います。

## スキルの場所と呼び出し

リポジトリのソーススキルは `skills/<skill-name>/` にあります。`setup_clients.py --apply` は、Codex 用に `.agents/skills/<skill-name>/`、Claude Code 用に `.claude/skills/<skill-name>/` へプロジェクト内コピーします。コピー後、Codex では `$houdini-scene-doctor` のように `$skill-name` を、Claude Code では `/houdini-scene-doctor` のように `/skill-name` を使って明示起動できます。関連する依頼では各クライアントが自動選択することもあります。

Claude Desktop は Claude Code とは別のアプリ設定を使います。このスクリプトが作成する `.mcp.json` や `.claude/skills/` は Claude Desktop の設定ではありません。Claude Desktop のローカル stdio サーバーは Desktop 側で別途設定またはインポートしてください。Claude の Web/Cowork/クラウドセッションも、このPCのローカル `.mcp.json` や stdio プロセスを自動的には利用しません。クラウド側で使うには、その実行環境へ提供されたコネクタとアカウントで有効なスキルが必要です。

## Houdini 作業の引き継ぎ

Codex と Claude Code で同じシーンを扱う場合、既存ノードをまず inspect/snapshot し、ユーザーが頼んだ範囲だけを最小限変更します。既存トポロジーの作り直しは依頼がある場合に限ります。

チャット間の継続には同じプロジェクト内 JSONL ジャーナルと node snapshot を使います。ユーザーが指定したジャーナルパスを使い、指定がなければ継続記録が依頼範囲に含まれるときに既存ディレクトリ内のプロジェクトパスを選びます。ジャーナルは Codex/Claude の自動メモリではありません。次のチャットでは記録を読み、変更を再実行する前に Houdini の現在状態を改めて確認します。

同じ Houdini GUI セッションを複数クライアントから使うときは、シーン変更を同時実行せず直列に行います。Batch は各要求が別 hython プロセスです。前の変更の `hip_output` を次の要求の `hip_input` に渡します。

## バージョン確認

この作業環境で確認した CLI バージョン: Codex `0.166.0-alpha.5.1`、Claude Code `2.1.316`。この記録は他のバージョンの互換性を保証するものではありません。

公式ドキュメント: [Codex MCP servers](https://learn.chatgpt.com/docs/extend/mcp?surface=cli), [Codex skills](https://learn.chatgpt.com/docs/build-skills), [Claude Code MCP](https://code.claude.com/docs/en/mcp), [Claude Code skills](https://code.claude.com/docs/en/skills).
