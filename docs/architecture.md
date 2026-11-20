# アーキテクチャ

## 処理経路

MCP クライアントは stdio 経由で `houdini-mcp` に JSON 対応ツール要求を送ります。サーバーは要求を検証して、選択されたバックエンドへ処理を渡します。Houdini 内で動く dispatcher は HOM の結果を JSON 値へ変換し、成功時は `{"ok": true, "result": ...}`、失敗時は `{"ok": false, "error": ...}` を返します。

### Batch

要求ごとに hython を起動し、プロトコル用ファイル経由で要求と応答を受け渡します。プロセス状態は呼び出し間で共有されません。必要なシーンは要求の `hip_input` で読み込み、変更を残したい場合は `hip_output` を明示します。出力が既に存在するときは `overwrite: true` がない限り上書きしません。

### GUI

起動済み Houdini に対し、`127.0.0.1` 上の HTTP で JSON 要求を送ります。GUI bootstrap と MCP は同じトークンファイルを読み取り、HMAC-SHA-256 で要求と応答を相互に検証します。時刻と使い捨ての要求 ID で再送を拒否し、トークン自体は HTTP に載せません。GUI は定義済みの操作を受け付け、同時接続数と要求サイズを制限します。

`reconnect` は対象 HIP のパス、未保存状態、セッション ID を返します。以降の呼び出しではセッション ID も照合し、別の Houdini セッションに切り替わった場合は変更を実行せずにエラーを返します。

HOM 操作は Houdini のメインスレッドで実行し、要求ごとに応答を保持します。`--timeout` は接続・応答待ちに適用されます。待機が終わった後も、Houdini に届いた処理は完了することがあります。

## 境界とエラー

- MCP サーバーと Houdini の間は JSON データを受け渡します。戻り値に HOM オブジェクトを含めず、必要な情報を文字列・数値・配列・辞書へ整形します。
- Python 実行は MCP の `--allow-python` と、GUI 使用時は bootstrap の `allow_python=True` の両方で有効にします。
- 入力には信頼できる HIP と HDA を使います。Houdini のロードや cook は、入力アセットのスクリプトを実行することがあります。標準ノードの検査は成果物の構成確認に使います。
- 実行エラーは MCP の `isError: true` と既存の JSON エラー詳細を返します。
- 新規ノードと HIP・HDA の標準保存経路では、コード記述で処理するノードとカスタム HDA の実行セクションを検査します。検査対象はノードの構造と型で、cook は行いません。同梱されたロック済み標準 HDA は利用できます。
- エラー応答は例外型、メッセージ、可能な場合は traceback を含み、部分的なシーン変更の可能性を記します。`node_cook` は cook が失敗しても Houdini の errors、warnings、messages を返します。
- GUI の変更操作は Houdini undo group 内で実行されます。操作エラー後は、部分変更の有無を調べてから修正します。
- タイムアウト後に変更操作を再試行すると二重実行の恐れがあります。自動再試行せず、状態を調べてから次の操作を判断します。

## 参考

- [SideFX HOM RPC](https://www.sidefx.com/docs/houdini/hom/rpc.html)
- [fxhoudinimcp のアーキテクチャ参考](https://github.com/healkeiser/fxhoudinimcp)

このプロジェクトは上記を概念上の参考としており、独立して実装しています。
