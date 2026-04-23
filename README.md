# RSS to Discord Bot

RSS フィードから記事を取得し、ランダムに1件選んでDiscordに投稿するシンプルなボットです。  
AWS Lambda と EventBridge Scheduler を使用して、定期的に記事を投稿します。

## プロジェクト概要

このボットは MVP として最小構成での実装を重視しており、以下の特徴があります：

- **シンプルな構成**: 複雑な状態管理や記事の重複チェックは行いません
- **エラー耐性**: 一部のRSSフィードが取得失敗しても、他のフィードで継続動作します  
- **完全自動化**: GitHub Actions による自動デプロイに対応しています

## 構成

```
AWS Lambda (Python 3.12)
    ↓ 定期実行 (毎時)
EventBridge Scheduler
    ↓ RSS取得
複数のRSSフィード
    ↓ ランダム選択・投稿
Discord Webhook
```

## 必要な設定

### GitHub Actions 使用時

#### GitHub Secrets

以下のシークレットを GitHub リポジトリに設定します：

- `AWS_ROLE_TO_ASSUME`: AWS OIDC 用の IAM ロール ARN
- `DISCORD_WEBHOOK_URL`: Discord の Webhook URL

#### GitHub Variables

以下の変数を GitHub リポジトリに設定します：

- `AWS_REGION`: AWS リージョン (例: `ap-northeast-1`)
- `SAM_STACK_NAME`: CloudFormation スタック名 (例: `rss-discord-bot`)


### Discord Webhook 設定

1. Discord サーバーの設定から「連携サービス」→「ウェブフック」を選択
2. 新しいウェブフックを作成
3. ウェブフック URL を `DISCORD_WEBHOOK_URL` シークレットに設定

## config.yaml の例

```yaml
# RSS フィード URL のリスト
rss_urls:
  - https://zenn.dev/feed
  - https://qiita.com/popular-items/feed
  - https://www.engadget.com/rss.xml
  - https://openai.com/news/rss.xml

# Discord 設定
discord:
  webhook_url_env: DISCORD_WEBHOOK_URL
  username: Hot Topics Bot

# 記事収集設定
collect:
  max_entries_per_feed: 5
```

## ローカル実行方法

### 前提条件

- Python 3.12
- pip

### 実行手順

1. 依存関係をインストール:
```bash
pip install -r requirements.txt
```

2. 環境変数を設定:
```bash
export DISCORD_WEBHOOK_URL="your_webhook_url_here"
```

3. ローカル実行:
```bash
cd src
python app.py
```

## AWS SAM を使用したデプロイ

### 前提条件

- AWS CLI がインストール・設定済み
- SAM CLI がインストール済み
- 適切な AWS 権限

### デプロイ手順

1. ビルド:
```bash
sam build
```

2. 初回デプロイ (ガイド付き):
```bash
sam deploy --guided
```

3. 通常のデプロイ:
```bash
sam deploy --parameter-overrides DiscordWebhookUrl="your_webhook_url_here"
```

### SAM 設定

`samconfig.toml.example` を `samconfig.toml` にコピーして、必要に応じて設定を変更します。

## GitHub Actions による自動デプロイ

`main` ブランチへの push または手動実行で、自動的にAWSにデプロイされます。

### 必要な権限

GitHub Actions が使用する AWS IAM ロールには、以下の権限が必要です：

- CloudFormation の作成・更新・削除
- Lambda 関数の作成・更新
- EventBridge Scheduler の作成・更新  
- IAM ロールの作成
- S3 (SAM デプロイ用バケット)

## 現在の制限・今後の拡張案

### MVP のため未実装の機能

- ✗ 投稿済み記事の重複チェック
- ✗ キーワードフィルタリング  
- ✗ ジャンル分類
- ✗ 複数件同時投稿

### 今後の拡張案

- **重複管理**: DynamoDB を使用した投稿済み記事の管理
- **フィルタ**: キーワードによる記事のフィルタリング機能
- **ジャンル分類**: 記事を自動分類してカテゴリ別投稿
- **複数件投稿**: 一度に複数記事をまとめて投稿
- **Web管理画面**: RSSフィードや設定をWebで管理
- **統計機能**: 投稿統計や人気記事の分析

## トラブルシューティング

### Lambda実行エラー

- CloudWatch Logs でエラーログを確認します
- タイムアウトの場合は `template.yaml` の `Timeout` を調整します

### RSS取得エラー  

- 特定のフィードが失敗しても他のフィードで継続されます
- 全フィードが失敗する場合は、ネットワーク設定を確認します

### Discord投稿エラー

- Webhook URL が正しく設定されているか確認します
- Discord サーバーの権限設定を確認します

## ライセンス

このプロジェクトは MIT ライセンスの下で公開されています。