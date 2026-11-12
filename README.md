# kikimimi-proto（聞き耳）

マイクの発話を日本語で書き起こし、Gemini Decision 1（Decisions API）で感情ごとの確率を出すプロトタイプ。

問い: Decision 1 は話し言葉のテキストと声色から、気持ちの推定を実用的な速さと確からしさで返せるか。

## 構成

- ブラウザ（Chrome / Edge）: Web Speech API で ja-JP の途中結果と確定結果を得る。確定ごとに MediaRecorder で区切った webm 音声も作る
- `server.py`: `/decide` が `POST https://generativelanguage.googleapis.com/v1beta/decisions` を呼ぶ。感情ごとに `noul`（yes/no 確率）の質問を一つずつ並べる
  - 途中結果: テキストだけ、応答待ちの間は最新の一件に置き換え
  - 確定結果: テキスト + 音声

## 認証

`GOOGLE_AI_STUDIO_KEY` があれば API キー（`x-goog-api-key`）。キーの API 制限に generativelanguage.googleapis.com が要る（aiplatform だけだと 403 API_KEY_SERVICE_BLOCKED）。

なければ ADC。generative-language スコープが要る（gcloud の通常トークンでは 403 ACCESS_TOKEN_SCOPE_INSUFFICIENT）。

```sh
gcloud auth application-default login \
  --scopes=https://www.googleapis.com/auth/cloud-platform,https://www.googleapis.com/auth/generative-language
```

課金・クォータのプロジェクトは `GOOGLE_CLOUD_PROJECT` で渡し、`x-goog-user-project` ヘッダになる。プロジェクトで Generative Language API が有効である必要がある。

## 起動

```sh
GOOGLE_AI_STUDIO_KEY=<key> ./server.py         # http://localhost:18960/
GOOGLE_CLOUD_PROJECT=<project-id> ./server.py   # ADC
```

google-genai SDK は使わない（decisions.create は 3.2 以降で、出てから 1 週間経っていない）。REST を直接呼ぶ。
