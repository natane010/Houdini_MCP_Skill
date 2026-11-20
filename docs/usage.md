# 使用方法

## ツール一覧

すべてのツールは JSON オブジェクトの入力を受け取ります。ノードパスは Houdini の絶対パス（例 `/obj/geo1`）を使います。`examples/` のファイルは worker/dispatcher に渡す内部エンベロープの例です。MCP クライアントからは表のツール名を選び、`op` と `args` を重ねずツール引数だけを渡します。

| ツール | 引数 | 用途 |
| --- | --- | --- |
| `connection_status` | なし | Houdini バージョンと HIP パスを確認。GUI では未保存状態とセッション ID も返す |
| `reconnect` | なし | GUI の接続先を認証して識別する。Batch では hython の設定を確認 |
| `execute_python` | `code` | 有効化時に任意 Python を実行 |
| `node_types` | `path` | ネットワークに作成可能な子ノード型名を列挙 |
| `node_create` | `parent`, `type_name`, `name?` | 子ノードを作成 |
| `node_inspect` | `path` | ノードの型、入力、パラメータを確認 |
| `node_snapshot` | `path`, `parm_names?`, `max_parms?` | 未評価の値、式、キー、入力・出力配線を取得 |
| `node_list` | `path` | 子ノードを列挙 |
| `node_set_parms` | `path`, `values`, `replace_driven?` | 指定ノード内のパラメータを設定 |
| `node_connect` | `path`, `source?`, `input_index?`, `output_index?` | 入力接続を設定。`source` 省略は接続解除 |
| `node_set_flags` | `path`, `display?`, `render?` | 出力ノードの表示・レンダーを指定 |
| `node_delete` | `path` | ノードを削除 |
| `node_cook` | `path` | cook して errors/warnings/messages を返す |
| `scene_load` | `path`, `discard_changes?` | 指定 hip ファイルを読み込む。GUI の未保存変更の破棄は明示が必要 |
| `scene_save` | `path`, `overwrite?` | 指定先へ hip を保存 |
| `hda_publish` | `path`, `output_path`, `type_name`, `description?` | 選択したネットワークを新しい HDA として公開 |
| `batch_edit_network` | `hip_input`, `hip_output`, `steps`, `overwrite?` | 一連の変更を同じ Batch シーンで行い、完成した HIP を保存 |

`node_inspect` は最大 1,000 個のパラメータタプルを評価し、名前、ラベル、型、サイズ、値を返します。上限を超える場合は `parms_truncated` が `true` になります。評価できない要素の値には `null` が入り、タプルの `evaluation_errors` にパラメータ名と理由が入ります。

変更前後の比較には `node_snapshot` を使います。`parm_names` には `tx` のような個別名と `t` のようなタプル名を混在できます。省略時は Houdini が返す順に最大 200 個のパラメータを記録します。`max_parms` は 1〜1,000 の範囲です。GUI と Batch の標準ツールとして利用できます。

複数要素タプルを設定するときは、要素数が一致する配列を `values` に渡します。参照・式・キーのある項目が含まれると、既定でその要求の書き込みを開始せず、`error.parameters` に対象パスと参照先などを返します。現在の式・アニメーションを消して対象だけを固定値に置き換える場合は、`replace_driven: true` を指定します。

Batch では `node_create`、`node_set_parms`、`node_connect`、`node_set_flags`、`node_delete`、`execute_python` に `hip_input`、`hip_output`、`overwrite` を指定できます。`node_inspect`、`node_snapshot`、`node_list`、`node_types`、`node_cook`、`scene_save`、`hda_publish` には `hip_input` を指定できます。GUI で未保存変更を破棄して `scene_load` する場合は `discard_changes: true` を指定します。

ツール実行に失敗すると、MCP は `isError: true` と JSON のエラー詳細を返します。`node_cook` で cook に失敗した場合も `isError: true` になり、`result` 内の `errors`、`warnings`、`messages` を確認できます。

## Batch で SOP ネットワークを作成・検証・保存する

各見出しのツールに JSON を引数として渡します。出力名は MCP サーバーの作業フォルダーに対する相対パスです。書き込み可能なフォルダーを使い、同名ファイルがある場合は別名を選んでください。

各変更ツールが返すトップレベルの `hip_output` を、次の呼び出しの `hip_input` にコピーします。Houdini のライセンスによって実際の拡張子は `.hipnc` や `.hiplc` になることがあります。

### 1. `node_create` で Geometry を作成

```json
{"parent":"/obj","type_name":"geo","name":"mcp_sop_demo","hip_output":"mcp_demo_01_geo.hip"}
```

### 2. `node_create` で Box を作成

```json
{"parent":"/obj/mcp_sop_demo","type_name":"box","name":"box1","hip_input":"mcp_demo_01_geo.hip","hip_output":"mcp_demo_02_box.hip"}
```

### 3. `node_create` で Null を作成

```json
{"parent":"/obj/mcp_sop_demo","type_name":"null","name":"OUT","hip_input":"mcp_demo_02_box.hip","hip_output":"mcp_demo_03_null.hip"}
```

### 4. `node_connect` で Box と Null を接続

```json
{"path":"/obj/mcp_sop_demo/OUT","source":"/obj/mcp_sop_demo/box1","hip_input":"mcp_demo_03_null.hip","hip_output":"mcp_demo_04_connected.hip"}
```

### 5. `node_cook` で Null を検証

```json
{"path":"/obj/mcp_sop_demo/OUT","hip_input":"mcp_demo_04_connected.hip"}
```

`result.cooked` が `true` であることを確認します。

### 6. `scene_save` で検証済み HIP を保存

```json
{"path":"mcp_sop_demo.hip","hip_input":"mcp_demo_04_connected.hip"}
```

検証に使った手順 4 の HIP を読み込み、`result.path` に保存先が返ります。

操作が途中で失敗した場合は、再作成する前に `node_list` と `node_inspect` で部分的な変更を確認します。

## 標準ノードで組む

固定属性には Attribute Create、乱数属性には Attribute Randomize、選択には Group Create、属性のクラス変換には Attribute Promote を使えます。利用できるノード型を `node_types` で確認してから配置します。

`node_create`、`scene_save`、Batch の `hip_output`、`hda_publish` では、Wrangle、VEX 式を入力する専用ノード、VOP の Inline Code、Python オペレータなどを検出します。拒否された場合、`error.code_nodes` に対象のパスと理由が入ります。Houdini に同梱されたロック済み標準 HDA は、そのノードを標準機能として利用できます。既存のコードノードは読み込みやパラメータの調査に利用できます。標準の保存・公開は、成果物内の該当ノードを標準ノードに置き換えてから実行します。

## コードノードを標準ノードへ置き換える

`error.code_nodes` の `candidate_types` には、その Houdini に存在する SOP の候補が入ります。他のネットワークでは `node_types` で候補を確認できます。`node_snapshot` で元の式・配線・表示フラグを確認し、必要な入出力と属性に合うノードを選びます。適合するノードが同じネットワークにある場合は、そのノードへ配線し直せます。

以下は固定のポイント属性 `pscale` を作る Wrangle を、Attribute Create に置き換える `batch_edit_network` の例です。例のパスとパラメータ名は対象シーンの確認結果に合わせます。

```json
{
  "hip_input": "legacy.hip",
  "hip_output": "standard_nodes.hip",
  "steps": [
    {"op":"node_create","args":{"parent":"/obj/geo1","type_name":"attribcreate","name":"create_pscale"}},
    {"op":"node_set_parms","args":{"path":"/obj/geo1/create_pscale","values":{"name1":"pscale","class1":2,"value1v1":0.2}}},
    {"op":"node_connect","args":{"path":"/obj/geo1/create_pscale","source":"/obj/geo1/source"}},
    {"op":"node_connect","args":{"path":"/obj/geo1/OUT","source":"/obj/geo1/create_pscale"}},
    {"op":"node_delete","args":{"path":"/obj/geo1/attribwrangle1"}},
    {"op":"node_cook","args":{"path":"/obj/geo1/OUT"}}
  ]
}
```

同じ要求に `node_create`、`node_set_parms`、`node_connect`、`node_set_flags`、`node_delete`、`node_cook` を最大100ステップ指定できます。ステップまたは cook の失敗時は `error.step` に番号を返します。コードノードが残っている場合も保存を拒否します。GUI では同じ操作を個別のツールから実行し、完成後に `scene_save` します。

## HDA 作成

`hda_publish` に対象サブネットと新しい絶対パスを渡します。Batch では対象を含む HIP を `hip_input` に指定します。

```json
{"path":"/obj/mcp_sop_demo","output_path":"C:/work/assets/mcp_sop_demo.hda","type_name":"studio::mcp_sop_demo::1.0","description":"SOP Demo","hip_input":"mcp_sop_demo.hip"}
```

出力先の親フォルダーは既存のものを使います。`result.output_path` に実際のライブラリのパスが返ります。対象ノードの型は維持されます。

## Cook エラーの調査

`node_cook` の結果からエラー・警告を取り出し、対象を `node_inspect` します。入力接続、ノード型、該当パラメータ、属性の存在と型を順に確認します。原因を修正した後、対象ノードを再 cook します。タイムアウトの後に再実行するときは先に現在の状態を検査し、操作が完了していないと判断できた場合だけ次の変更を行います。

## 保存と上書き

Batch でノード変更を保存するには `hip_output` を指定します。Batch の `scene_save` は `hip_input` で読み込んだシーンを `path` へ保存し、GUI の `scene_save` は現在のシーンを `path` へ保存します。既存ファイルの上書きには `overwrite: true` が必要です。
