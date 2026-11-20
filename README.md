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
.venv\Scripts\python.exe -m pip install --upgrade pip
.venv\Scripts\python.exe -m pip install -e .
.venv\Scripts\houdini-mcp.exe --backend batch --hython "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe"
```

上記パスは実際の Houdini インストールに合わせてください。GUI バックエンドでは Houdini の Python Shell で次を実行してから、MCP を `--backend gui` で起動します。複数セッションの設定例は [クライアント連携の手順](docs/clients.md#gui-バックエンド) を参照してください。

```python
import runpy
gui = runpy.run_path(r"E:\Projects\HoudiniMCP\scripts\start_gui_loopback.py")
houdini_mcp_gui = gui["start_server"]()
```

接続の照合にはポートごとのトークンファイルを使います。`reconnect` または `connection_status` で HIP パス、未保存状態、セッション ID を確認できます。

## Codex / Claude Code 連携

クライアントごとのプロジェクト設定、dry run、明示的な適用方法は [docs/clients.md](docs/clients.md) を参照してください。`scripts/setup_clients.py` は既定では計画 JSON のみを表示し、`--apply` のときだけプロジェクト内の設定とスキルを配置します。

## Houdini 作業スキル

リポジトリ内のスキルは [docs/skills.md](docs/skills.md) に一覧があります。プロジェクトに設定すると、Codex は `$skill-name`、Claude Code は `/skill-name` で呼び出せます。スキルは `SKILL.md` と同梱の `references/`・`scripts/` をまとめて保ってください。

既存ノードのチューニングでは、標準ツール `node_snapshot` で式・キー・配線を記録してから変更します。参照・式・キーのあるパラメータに対する `node_set_parms` は既定で拒否し、対象パスと参照先を返します。

MCP で作成・保存する HIP と HDA は、標準ノードと配線で構成します。Wrangle・Inline Code・Python ノードなどは作成時に拒否し、保存と `hda_publish` でも完成したネットワークを検査します。

既存のコードノードを置き換える場合は、検出結果の候補と `node_snapshot` で配線・パラメータを確認します。Batch では `batch_edit_network` で配線の変更、旧ノードの削除、cook を一度に実行できます。[標準ノードへの置き換え例](docs/usage.md#コードノードを標準ノードへ置き換える)

チャットをまたいで Houdini の作業判断を引き継ぐときは、プロジェクト内の JSONL 記録先を明示して `$houdini-iterate` を使います。Codex の自動メモリには保存されず、後続のチャットでは同じファイルを読み直します。詳細は [docs/skills.md](docs/skills.md) を参照してください。

Python 実行ツールを使う場合に限り `--allow-python` を追加します。GUI では bootstrap 側でも `start_server(allow_python=True)` が必要です。任意 Python から直接ファイルを出力すると検査を経由しないため、成果物は標準の保存・公開ツールで出力します。

## バックエンド選択

| バックエンド | 適した用途 | シーンの扱い |
| --- | --- | --- |
| `batch` | 再現可能な処理、GUI 不要の生成・検査 | 呼び出しごとの hython プロセス。`hip_input` で読み、`hip_output` を指定した場合だけ明示先へ保存 |
| `gui` | ビューポート、インタラクティブな状態、UI が必要な作業 | 起動中の Houdini と接続。タイムアウトは GUI 側の処理をキャンセルしない |

利用可能なツールと JSON 例は [docs/usage.md](docs/usage.md) を参照してください。構成は [docs/architecture.md](docs/architecture.md)、テスト手順は [docs/testing.md](docs/testing.md)、今回の確認結果と未検証範囲は [docs/verification.md](docs/verification.md) にあります。

## 運用上の注意

GUI のトークンファイルはユーザー専用のフォルダーに置きます。GUI 通信はローカルに限定し、要求と応答を署名で確認します。入力する HIP と HDA は、信頼できる配布元のものを使ってください。旧バージョンで起動した GUI の RPC を使っている場合は、Houdini を再起動してから新しい bootstrap を読み込んでください。タイムアウト後に変更を再試行する前に、`connection_status` や `node_snapshot` で現在の状態を確認してください。

このリポジトリは独立した実装です。設計上の参考として [fxhoudinimcp](https://github.com/healkeiser/fxhoudinimcp) と [SideFX HOM RPC](https://www.sidefx.com/docs/houdini/hom/rpc.html) を参照しています。
