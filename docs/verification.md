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

初回検証時にはクライアント設定の変更は行いませんでした。追加整備後のプロジェクト内配置については以下を参照してください。

## 追加 Skill とクライアント連携の検証

同日、次の5つを追加し、既存の `houdini-procedural` と合わせて6つの Skill にしました。

- `houdini-scene-doctor`: cook しない構造・式・既存診断の取得。ノード数とパラメータ数に上限。
- `houdini-vex-workbench`: VEX の制作、属性の型とクラスの検証。
- `houdini-hda-publisher`: 新規 HDA の作成、元ノード型の維持、出力先・型名の衝突防止。
- `houdini-cop-workbench`: Copernicus と旧 COP2 の区別、COP の作成と既存 Blur の調整。
- `houdini-iterate`: ノードの未評価スナップショット、変更前後の比較、判断と検証結果の JSONL 記録。

追加後の全テストは **25 passed in 44.55s**。Houdini を起動するテストは、一時的なユーザー設定フォルダーを使い、テスト用 subprocess のみ package・ユーザー env の読み込みを無効化しています。製品バックエンドの起動環境は変更していません。

追加の実機確認結果:

- 既存 box → wrangle → OUT の wrangle だけを調整し、ノードの session ID と接続を維持。8点・6プリミティブ、変化のある point `pscale` / `Cd`、エラー・警告なし。
- Copernicus `copnet` の `constant` → `blur` を64×64で検証。1チャンネル、Rawレイヤー、エラー・警告なし。既存 Blur の `size` を 0.005 から 0.002 へ変更し、入力接続を維持。
- スナップショットは `1 / 0` の式、アニメーションキー、`$HIP` とバッククォートを含む文字列を未評価で取得し、cook 回数は不変。
- ジャーナルは Unicode の追記・順序を維持し、不完全な行への追記、相対パス、不正な JSON 定数、過大な記録を拒否。
- 6つすべての Skill が形式検証に成功。

`setup_clients.py` の dry run と一時プロジェクトでの適用、設定保持、再実行、衝突時の事前拒否をテストしました。その後、このローカル作業コピーへ Batch / `--allow-python` のプロジェクト設定を適用しています。

- Codex `0.166.0-alpha.5.1`: `codex mcp get houdini --json` で設定と `enabled=true` を確認。
- Claude Code `2.1.316`: `claude mcp get houdini` が Project config として認識。初回の利用承認は Pending approval。
- 同じ設定で再度 dry run すると、書き込み予定・コピー予定とも空。

生成した `.codex/config.toml`、`.mcp.json`、`.agents/skills/`、`.claude/skills/` はローカル用途で Git 管理対象外です。ユーザー全体の設定は変更していません。クライアント内の実際の AI 会話による操作、Houdini GUI の実機操作、他のバージョンや OS は未検証です。[クライアント導入手順](clients.md) を参照してください。
