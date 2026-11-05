# 使用方法

## ツール一覧

すべてのツールは JSON オブジェクトの入力を受け取ります。ノードパスは Houdini の絶対パス（例 `/obj/geo1`）を使います。`examples/` のファイルは worker/dispatcher に渡す内部エンベロープの例です。MCP クライアントからは表のツール名を選び、`op` と `args` を重ねずツール引数だけを渡します。

| ツール | 引数 | 用途 |
| --- | --- | --- |
| `connection_status` | なし | 接続状態、Houdini バージョン、hip パスを確認 |
| `reconnect` | なし | GUI 接続を再確立 |
| `execute_python` | `code` | 有効化時に任意 Python を実行 |
| `node_types` | `path` | ネットワークに作成可能な子ノード型名を列挙 |
| `node_create` | `parent`, `type_name`, `name?` | 子ノードを作成 |
| `node_inspect` | `path` | ノードの型、入力、パラメータを確認 |
| `node_list` | `path` | 子ノードを列挙 |
| `node_set_parms` | `path`, `values` | パラメータを設定 |
| `node_connect` | `path`, `source?`, `input_index?`, `output_index?` | 入力接続を設定。`source` 省略は接続解除 |
| `node_delete` | `path` | ノードを削除 |
| `node_cook` | `path` | cook して errors/warnings/messages を返す |
| `scene_load` | `path`, `discard_changes?` | 指定 hip ファイルを読み込む。GUI の未保存変更の破棄は明示が必要 |
| `scene_save` | `path`, `overwrite?` | 指定先へ hip を保存 |

`node_inspect` の `parms` は各パラメータタプルの名前、ラベル、型、サイズ、値を返します。複数要素タプル（例: `t` や Box SOP の `size`）を設定するときは `values` に配列を渡します。単一値には scalar を渡します。

ツールの一覧や入力スキーマがサーバー実装で提供される場合は、クライアントのツール定義を優先してください。Batch では `node_create`、`node_set_parms`、`node_connect`、`node_delete`、`execute_python` に `hip_input`、`hip_output`、`overwrite` を指定できます。`node_inspect`、`node_list`、`node_types`、`node_cook` には `hip_input` を指定できます。`scene_load` は GUI に未保存変更がある場合、既定では拒否します。変更を破棄してよい場合だけ `discard_changes: true` を指定してください。

## 手順: SOP ネットワークを非破壊で作る

1. `connection_status` で対象 Houdini を確認します。
2. Batch では入力 hip を `hip_input` に指定し、新しい出力先を `hip_output` に指定します。GUI では対象 hip の状態を確認してから作業します。
3. `/obj` の子を `node_list` で調べ、既存ネットワークを上書きしない専用 Geometry コンテナ名を選びます。
4. Geometry コンテナと SOP ノードを `node_create` で作成し、`node_connect` で接続します。
5. 各ノードを `node_inspect` してパラメータ名・型を確認してから `node_set_parms` を使います。
6. 最終ノードを `node_cook` し、エラーと警告を確認します。成功を確認してから明示した出力先へ保存します。

操作が途中で失敗した場合は、再作成する前に `node_list` と `node_inspect` で部分的な変更を確認します。

## VEX wrangle の型検証

Wrangle のコードやパラメータを設定する前に `node_inspect` し、Wrangle ノードの種類、入力数、既存パラメータを確認します。Attribute Wrangle は通常 Geometry SOP 配下です。`node_set_parms` で設定した後に `node_cook` を呼び、Houdini のコンパイル・実行エラーを確認します。`node_inspect` は geometry 属性の一覧を返さないため、属性クラス・型・サンプル値は [workflows.md の geometry 確認例](../skills/houdini-procedural/references/workflows.md#vex-wrangle-and-geometry-checks) を使って HOM から確認します。

Python が有効な環境では VEX の式を Python として実行しないでください。`execute_python` は HOM/Python 操作用です。

## HDA 作成

HDA 作成は定義ファイルや Houdini の登録状態を変更します。HOM の具体例はスキル同梱の [workflows.md](../skills/houdini-procedural/references/workflows.md#hda-from-a-subnet) を参照してください。新しい出力パスを選び、既存ライブラリを上書きしないでください。SideFX API: [hou.OpNode.createDigitalAsset](https://www.sidefx.com/docs/houdini/hom/hou/OpNode.html)。

## Cook エラーの調査

`node_cook` の結果からエラー・警告を取り出し、対象を `node_inspect` します。入力接続、ノード型、該当パラメータ、属性の存在と型を順に確認します。原因を修正した後、対象ノードを再 cook します。タイムアウトの後に再実行するときは先に現在の状態を検査し、操作が完了していないと判断できた場合だけ次の変更を行います。

## 保存と上書き

Batch は `hip_output` がない限り変更結果を hip に保存しません。GUI の `scene_save` は指定パスへ保存します。既存ファイルの上書きには `overwrite: true` が必要です。ユーザーが明示した出力先以外への保存や、変更の自動再試行は行わないでください。
