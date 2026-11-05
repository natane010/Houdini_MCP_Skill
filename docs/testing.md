# テストと手動確認

## Python テスト

開発依存を入れてからリポジトリルートで実行します。

```powershell
py -m pip install -e ".[test]"
py -m pytest
```

`hython` 統合テストは同じ pytest 実行内で動き、`HOUDINI_MCP_TEST_HYTHON` で実行ファイルを指定できます。変数を省略すると既定の Houdini 22.0.368 パスを使います。選択されたパスにファイルがない場合、hython 統合テストは skip されます。

```powershell
$env:HOUDINI_MCP_TEST_HYTHON = "C:\Program Files\Side Effects Software\Houdini 22.0.368\bin\hython.exe"
py -m pytest
```

## 手動確認の観点

- サーバーが stdio MCP として起動し、ツール一覧と入力スキーマを返す。
- Batch 要求が別々の hython プロセスで実行され、`hip_input` を読み込む。
- `hip_output` 未指定では入力 hip を変更せず、指定時は新しい出力へ保存する。
- 既存の hip 出力先は `overwrite: true` がない限り保護される。
- GUI は `scripts/start_gui_loopback.py` から接続し、RPC ポートが `127.0.0.1` のみに bind する。
- `scene_load` は GUI の未保存変更がある場合に既定で拒否し、`discard_changes: true` のときだけ置換する。
- `--allow-python` がない場合、Python 実行要求が拒否される。
- 存在しないノード、無効なパラメータ、cook エラーが構造化されたエラー情報になる。
- GUI 処理がタイムアウトしたとき、その実処理がキャンセルされたとは扱わず、状態を照会する。

利用可能な追加 pytest オプションは `py -m pytest --help` を確認してください。
