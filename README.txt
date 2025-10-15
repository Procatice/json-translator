# json-translator
🔹 事前準備
Python環境を用意
Python 3.7以上推奨
必要なライブラリをインストール
pip install deepl
DeepL APIキーを取得
DeepL ProアカウントでAPIキーを入手
環境変数 DEEPL_API_KEY に設定
export DEEPL_API_KEY="あなたのAPIキー"

（Windowsの場合は set DEEPL_API_KEY="あなたのAPIキー"）
🔹 スクリプトの準備
翻訳したいJSONファイルを用意
デフォルトでは mods.json が入力ファイル
出力は mods_jp.json に保存されます
翻訳対象のキーを確認
keys_to_translate = ['text','val']

JSON内のどのキーを翻訳するかを設定できます
翻訳設定を変更可能
translate_only_first：先頭n件だけ翻訳するか
batch_size：まとめて翻訳する件数
delay：API呼び出し間隔（秒）
🔹 実行方法
ターミナルでスクリプトのあるディレクトリに移動
実行
python translate_json.py

完了すると mods_jp.json に翻訳済みJSONが生成される
括弧や角括弧内、顔文字・記号は元のまま保持されます
バッチ処理と遅延制御でAPI負荷も考慮しています
🔹 使い方のポイント
小規模ファイルでテスト → まずは翻訳対象のJSONが正しく動作するか確認
バッチ・遅延設定 → 大きなファイルでは設定を調整してAPI制限に対応
翻訳対象キー → JSON構造によって追加可能
