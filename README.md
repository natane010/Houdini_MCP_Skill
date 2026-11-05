# Houdini MCP Bridge

Houdini をローカルの MCP クライアントから操作するための stdio ブリッジです。MCP サーバーは Python 側で動き、Houdini の HOM 操作は `hython` の独立プロセスまたは起動済み Houdini GUI に委譲します。

## 必要なもの

- Python 3.10 以上
- SideFX Houdini の同一インストールに付属する `hython`
- stdio MCP に対応した MCP クライアント

## インストールと起動

リポジトリのルートで仮想環境を作り、開発用インストールを行います。

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\houdini-mcp.exe --backend batch --hython "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe"
```

MCP クライアントの stdio 設定例:

```json
{
  "mcpServers": {
    "houdini": {
      "command": "E:\\Projects\\HoudiniMCP\\.venv\\Scripts\\houdini-mcp.exe",
      "args": ["--backend", "batch", "--hython", "C:\\Program Files\\Side Effects Software\\Houdini 22.0.368\\bin\\hython.exe"]
    }
  }
}
```

上記パスは実際の Houdini インストールに合わせてください。GUI バックエンドでは Houdini の Python Shell で bootstrap を読み込んでから、`--backend gui --port 18811` で接続します。

```python
exec(open(r"E:\Projects\HoudiniMCP\scripts\start_gui_loopback.py", encoding="utf-8").read())
```

`--port` を変える場合は bootstrap の `port` も同じ値にします。bootstrap はローカル用途専用です。

## Houdini 作業スキル

リポジトリ内の `skills/houdini-procedural/` は再利用できる Codex スキルです。使う環境に配置する場合はフォルダー全体を `~/.codex/skills/houdini-procedural/` にコピーし、Codex で `$houdini-procedural` と指定します。このリポジトリだけで使う場合はコピー不要です。

Python 実行ツールを使う場合に限り `--allow-python` を追加します。このフラグは利便性のためのゲートであり、Python コードを隔離するサンドボックスではありません。

## バックエンド選択

| バックエンド | 適した用途 | シーンの扱い |
| --- | --- | --- |
| `batch` | 再現可能な処理、GUI 不要の生成・検査 | 呼び出しごとの hython プロセス。`hip_input` で読み、`hip_output` を指定した場合だけ明示先へ保存 |
| `gui` | ビューポート、インタラクティブな状態、UI が必要な作業 | 起動中の Houdini と接続。タイムアウトは GUI 側の処理をキャンセルしない |

利用可能なツールと JSON 例は [docs/usage.md](docs/usage.md) を参照してください。構成は [docs/architecture.md](docs/architecture.md)、テスト手順は [docs/testing.md](docs/testing.md)、今回の確認結果と未検証範囲は [docs/verification.md](docs/verification.md) にあります。

## 運用上の注意

GUI 接続はローカルの信頼できるプロセス向けです。RPC サーバーは認証を提供しないため、ネットワークへ公開しないでください。タイムアウト後に変更操作を自動再試行しないでください。結果が不明なときは、まず `connection_status` や `node_inspect` で状態を調べます。保存やノード削除など永続・破壊的な操作は、対象と保存先を明示して実行してください。

このリポジトリは独立した実装です。設計上の参考として [fxhoudinimcp](https://github.com/healkeiser/fxhoudinimcp) と [SideFX HOM RPC](https://www.sidefx.com/docs/houdini/hom/rpc.html) を参照しています。
