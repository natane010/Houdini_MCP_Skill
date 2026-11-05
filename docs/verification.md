# 検証記録

2026-11-05、Windows のローカル作業コピーで実施しました。

## 実行環境

- MCP 側: Python 3.12.11、mcp 1.30.0、RPyC 4.1.0
- Houdini 側: Houdini 22.0.368、付属 hython / Python 3.13.10
- 参考リポジトリ: [fxhoudinimcp](https://github.com/healkeiser/fxhoudinimcp)、調査時コミット `bbee6b82691d91cfc3c295387847e82404d8b5b8`

## 確認できたこと

`.venv/Scripts/python.exe -m pytest -q` は **13 passed in 54.15s** でした。

- stdio MCP の初期化、ツール一覧、構造化された設定エラー
- Python 実行の有効化フラグ、接続断と再接続設定、タイムアウト処理
- 標準出力の上限、worker 障害時ログ末尾の取得
- 実際の hython での HIP 保存・再読み込み、出力先の上書き防止
- ノード型の列挙、作成・検査、パラメータタプルの変更
- SOP の接続・cook・削除、不正な VEX の cook 診断

別途、一時的なループバック RPC サーバーを hython 内で起動し、ローカル RPyC から接続して Houdini バージョンの取得と Python の実行結果 `42` を確認しました。テスト専用プロセスは終了・回収しています。

Skill の SOP / VEX / HDA 作例も一時的な Houdini 設定・出力先で実行しました。8 点・6 プリミティブ、`pscale` 属性（Float、1 要素、値約 0.1）、cook エラー・警告なしを確認しました。HDA ライブラリには `studio::mcp_geo_tool::1.0` 定義が生成され、元の subnet の型は維持されました。

`skill-creator` の `quick_validate.py`、サンプル JSON の読み込み、wheel のビルドも成功しています。wheel はリポジトリ外の一時フォルダーへ生成しました。

## 未検証の範囲

- 起動中の Houdini GUI での操作、メインスレッドへの実際のディスパッチ、Undo、未保存シーンの保護
- Houdini 22.0.368 以外のバージョン、別 OS
- GitHub Actions 上の実行（CI 定義は追加済み）

GUI のタイムアウトは Houdini 内の処理を取り消しません。失敗やタイムアウト後は部分的な変更の可能性があるため、状態を確認してから次の操作を行います。複数の変更を一括してロールバックするトランザクションは提供していません。

クライアントの MCP 設定やグローバル Skill 配置は変更していません。利用開始には [README](../README.md) の接続・配置手順を使用してください。
