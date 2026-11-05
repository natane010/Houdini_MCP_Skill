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

上記パスは実際の Houdini インストールに合わせてください。クライアントごとのプロジェクト設定は [docs/clients.md](docs/clients.md) を参照してください。GUI バックエンドでは Houdini の Python Shell で bootstrap を読み込んでから、`--backend gui --port 18811` で接続します。

```python
exec(open(r"E:\Projects\HoudiniMCP\scripts\start_gui_loopback.py", encoding="utf-8").read())
```

`--port` を変える場合は bootstrap の `port` も同じ値にします。bootstrap はローカル用途専用です。

## Codex / Claude Code 連携

クライアントごとのプロジェクト設定、dry run、明示的な適用方法は [docs/clients.md](docs/clients.md) を参照してください。`scripts/setup_clients.py` は既定では計画 JSON のみを表示し、`--apply` のときだけプロジェクト内の設定とスキルを配置します。

## Houdini 作業スキル

リポジトリ内のスキルは [docs/skills.md](docs/skills.md) に一覧があります。プロジェクトに設定すると、Codex は `$skill-name`、Claude Code は `/skill-name` で呼び出せます。スキルは `SKILL.md` と同梱の `references/`・`scripts/` をまとめて保ってください。

既存ノードのチューニングでは、設定と配線を確認してから最小限の変更を加えることを標準にしています。ネットワーク構成の作り直しは、依頼に含まれる場合に限ります。

チャットをまたいで Houdini の作業判断を引き継ぐときは、プロジェクト内の JSONL 記録先を明示して `$houdini-iterate` を使います。Codex の自動メモリには保存されず、後続のチャットでは同じファイルを読み直します。詳細は [docs/skills.md](docs/skills.md) を参照してください。

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
