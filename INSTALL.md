# インストール手順（他のMuse／エージェント向け）

このリポジトリを見たエージェントが、そのままの順序で導入を完了できるように書いた手順。各ステップに確認方法と期待結果がある。全部通れば導入完了。

前提：Linux x86_64、約3GBの空き、ffmpeg と 7z（p7zip）が使えること、Google Sheetsコネクタ（または同等のシート書き込み手段）が使えること。

## 0. 振る舞いの取り込み

最初に `AGENT_RULES.md` を読み、その内容を自分のメモリ／振る舞い設定に取り込むこと。口調・トリガー・合図送信の契約はそちらが正本。

## 1. VOICEVOXエンジンの導入

```bash
bash scripts/setup.sh ~/workspace/voicevox
```

やっていること（手動でも可）：

1. GitHubリリースから `voicevox_engine-linux-cpu-x64-0.26.0.7z.001`（1,848,012,250バイト）をダウンロード
   `https://github.com/VOICEVOX/voicevox_engine/releases/download/0.26.0/voicevox_engine-linux-cpu-x64-0.26.0.7z.001`
2. `7z x` で展開（展開先に `run` ができる）
3. `cd <展開先> && ./run --host 127.0.0.1 --port 50021` をバックグラウンド起動

確認：

```bash
curl -s http://127.0.0.1:50021/version        # -> "0.26.0"
curl -s http://127.0.0.1:50021/speakers | grep -o 'ずんだもん'  # -> 見つかる
```

話者「ずんだもん」のノーマルは **スタイルID 3**。VM再起動後はエンジンも落ちるので、手順3のコマンドで再起動すること。

## 2. フレーズ音声の合成

```bash
python3 scripts/synthesize_samples.py ~/workspace/zundamon-talk/samples-voicevox
```

確認：全33件（32＋トリガー用）が `kana_ok: True` で、最後に `ALL OK: True` と出ること。各サンプルのカナに `ノダ` があり `ノダッ` が無いこと、長さ0.5–4秒をスクリプトが自動判定する。**このチェックを通らない音声は使わない。**

## 3. 無音キープアライブの生成

```bash
bash scripts/make_keepalive.sh ~/workspace/zundamon-talk/keepalive.mp3
```

4秒の無音mp3。待機ページが「再生中のページ」として生き続けるために使う。

## 4. 状態スプレッドシートの用意

1. Googleスプレッドシートを新規作成（名前は任意、例：ずんだもん待機ページ状態）。
2. 1行目に `seq` `slug` `updated`、2行目に `0`（空）（空）を書く。
3. 共有を「リンクを知っている全員が閲覧可（閲覧者）」にする。**編集は自分（書き込み用アカウント）だけ**でよい。
4. スプレッドシートIDを控える。

確認：

```bash
curl -s "https://docs.google.com/spreadsheets/d/<SHEET_ID>/gviz/tq?sheet=シート1&range=A1:C2"
# -> google.visualization.Query.setResponse({... "seq" ... "0" ...}) が返る
```

## 5. 待機ページのビルド

```bash
python3 scripts/build_standby.py page/standby_template.html \
  ~/workspace/zundamon-talk/samples-voicevox ~/workspace/zundamon-talk/keepalive.mp3 \
  <SHEET_ID> ~/workspace/zundamon-talk/zundamon-standby.html
```

確認：生成HTMLが約320KBで、`data:audio/mpeg;base64` が34件（33サンプル＋キープアライブ）含まれること。

## 6. 状態ファイルの初期化

`zundamon-voice-state.example.json` を自分のワークスペースにコピーし、`sheet_id` を手順4のIDに書き換え、`enabled` は `false` で始める。パスは `AGENT_RULES.md` の契約どおり全チャット共通の場所に置く。

## 7. 疎通テスト

1. `ZUNDAMON_SHEET_ID=<SHEET_ID> scripts/push.sh ryoukai` を実行 → `pushed seq=1 slug=ryoukai` と出る。
2. 手順4の確認curlで、2行目が `1 / ryoukai / <時刻>` になっていることを読む。
3. 生成した待機ページをスマホの本物のChromeで開き、「音を有効にする」をタップ → 確認で「了解なのだ」が鳴る。
4. チャットアプリと分割画面にし、この手順を実行しているチャットからもう一度 `push.sh dekita` → 数秒後に「できたのだ」が鳴れば導入完了。

## 既知の制約（READMEの実機検証表も参照）

- ページが完全に背面（他のアプリの裏）だと、端末の背面制限で凍って鳴らないことが多い。**分割画面でページを見せたまま使うのが正解**。
- ナビ等の音声が割り込むと再生が止まることがある。ページ側に最大4回の鳴らし直しが入っているが、ページ自体が眠らされている場合は効かない。
- 画面オフ・長時間放置ではタブが破棄される。再開はページを開き直して有効化から。
