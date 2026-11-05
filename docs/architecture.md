# アーキテクチャ

## 処理経路

MCP クライアントは stdio 経由で `houdini-mcp` に JSON 対応ツール要求を送ります。サーバーは要求を検証して、選択されたバックエンドへ処理を渡します。Houdini 内で動く dispatcher は HOM の結果を JSON 値へ変換し、成功時は `{"ok": true, "result": ...}`、失敗時は `{"ok": false, "error": ...}` を返します。

### Batch

要求ごとに hython を起動し、プロトコル用ファイル経由で要求と応答を受け渡します。プロセス状態は呼び出し間で共有されません。必要なシーンは要求の `hip_input` で読み込み、変更を残したい場合は `hip_output` を明示します。出力が既に存在するときは `overwrite: true` がない限り上書きしません。

### GUI

起動済み Houdini にプロジェクト bootstrap が登録する RPC 接続を通じて要求を実行します。Houdini Python Shell から `scripts/start_gui_loopback.py` を実行します。この bootstrap は `127.0.0.1` に bind します。SideFX 標準の `hrpyc.start_server` は全インターフェースへ bind するため、そのまま使用しないでください。hrpyc RPC は認証を行わず、タイムアウトは実行中の Houdini 処理のキャンセルを意味しません。GUI のポートは信頼できるローカル環境だけで使用してください。

## 境界とエラー

- MCP サーバーと Houdini の間は JSON データを受け渡します。戻り値に HOM オブジェクトを含めず、必要な情報を文字列・数値・配列・辞書へ整形します。
- Python 実行は `--allow-python` の明示的な有効化が必要です。任意コード実行の隔離・安全性を保証するものではありません。
- エラー応答は例外型、メッセージ、可能な場合は traceback を含み、部分的なシーン変更の可能性を記します。`node_cook` は cook が失敗しても Houdini の errors、warnings、messages を返します。
- GUI の変更操作は Houdini undo group 内で実行されます。操作エラー後は、部分変更の有無を調べてから修正します。
- タイムアウト後に変更操作を再試行すると二重実行の恐れがあります。自動再試行せず、状態を調べてから次の操作を判断します。

## 参考

- [SideFX HOM RPC](https://www.sidefx.com/docs/houdini/hom/rpc.html)
- [fxhoudinimcp のアーキテクチャ参考](https://github.com/healkeiser/fxhoudinimcp)

このプロジェクトは上記を概念上の参考としており、独立して実装しています。
