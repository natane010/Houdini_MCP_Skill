# テストと手動確認

## Python テスト

Git で取得した作業コピーのルートで、開発依存を入れてから実行します。テストはリポジトリのセットアップスクリプトやスキル資産を使います。

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
- Wrangle、Python ノードなどを含むネットワークの HIP 保存と HDA 公開は拒否される。標準ノードのネットワークは `hda_publish` で公開できる。
- `batch_edit_network` で代替ノードを作成または再利用し、配線・表示フラグを設定できる。cook ステップに失敗した場合は保存を中止する。
- GUI は `scripts/start_gui_loopback.py` から接続し、ポートは `127.0.0.1` のみに bind する。無効なトークン、未定義の操作、別セッションへの変更は拒否される。
- GUI の `reconnect` と `connection_status` は、HIP パス、未保存状態、セッション ID を返す。
- `scene_load` は GUI の未保存変更がある場合に既定で拒否し、`discard_changes: true` のときだけ置換する。
- `--allow-python` を指定した場合にだけ、MCP のツール一覧に `execute_python` が表示される。
- `node_snapshot` は `--allow-python` なしで値・式・キー・配線を未評価のまま返す。保護された項目の編集は参照先も含めて報告し、MCP の `isError` が `true` になる。
- 存在しないノード、無効なパラメータ、cook エラーが構造化されたエラー情報になる。
- GUI 処理がタイムアウトしたとき、その実処理がキャンセルされたとは扱わず、状態を照会する。

利用可能な追加 pytest オプションは `py -m pytest --help` を確認してください。
