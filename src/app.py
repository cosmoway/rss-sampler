"""
RSS フィードから記事を取得し、ランダムに1件選んでDiscordに投稿するLambda関数
"""
import json
import logging
import os
import random
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional

import feedparser
import requests
import yaml

# ロガーの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

REQUEST_TIMEOUT = 10  # HTTPリクエストタイムアウト（秒）
MAX_CONTENT_LENGTH = 1024  # Discord投稿時の文字数制限を考慮


def load_config() -> Dict[str, Any]:
    """config.yaml を読み込む"""
    config_path = Path(__file__).parent / "config.yaml"
    
    if not config_path.exists():
        raise FileNotFoundError(f"config.yaml が見つかりません: {config_path}")
    
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        
        # 必須項目の確認
        required_keys = ['rss_urls', 'discord', 'collect']
        for key in required_keys:
            if key not in config:
                raise ValueError(f"config.yaml に必須項目 '{key}' がありません")
        
        logger.info("config.yaml を正常に読み込みました")
        return config
    
    except yaml.YAMLError as e:
        raise ValueError(f"config.yaml の解析に失敗しました: {e}")


def collect_entries(config: Dict[str, Any]) -> List[Dict[str, str]]:
    """RSSフィードから記事を収集する"""
    entries = []
    max_entries_per_feed = config['collect']['max_entries_per_feed']
    
    for rss_url in config['rss_urls']:
        logger.info(f"RSS取得開始: {rss_url}")
        
        try:
            # フィード取得
            feed = feedparser.parse(rss_url)
            
            if feed.bozo and feed.bozo_exception:
                logger.warning(f"RSS解析警告: {rss_url} - {feed.bozo_exception}")
            
            # フィード名を取得（フィード情報から、なければURLから）
            feed_title = getattr(feed.feed, 'title', rss_url)
            
            # エントリを収集
            count = 0
            for entry in feed.entries:
                if count >= max_entries_per_feed:
                    break
                
                # 必須項目をチェック
                if not hasattr(entry, 'title') or not entry.title:
                    logger.warning(f"記事のタイトルが空です: {rss_url}")
                    continue
                
                if not hasattr(entry, 'link') or not entry.link:
                    logger.warning(f"記事のリンクが空です: {rss_url}")
                    continue
                
                entries.append({
                    'title': entry.title,
                    'link': entry.link,
                    'source': feed_title
                })
                count += 1
            
            logger.info(f"RSS取得成功: {rss_url} - {count}件収集")
        
        except Exception as e:
            logger.warning(f"RSS取得失敗: {rss_url} - {e}")
            continue
    
    logger.info(f"収集完了: 合計 {len(entries)} 件の記事")
    return entries


def pick_random_entry(entries: List[Dict[str, str]]) -> Optional[Dict[str, str]]:
    """記事リストからランダムに1件選ぶ"""
    if not entries:
        logger.info("選択可能な記事がありません")
        return None
    
    selected = random.choice(entries)
    logger.info(f"選択された記事: {selected['title']}")
    return selected


def post_to_discord(entry: Dict[str, str], config: Dict[str, Any]) -> None:
    """Discord Webhookに記事を投稿する"""
    webhook_url_env = config['discord']['webhook_url_env']
    username = config['discord']['username']
    
    # Webhook URLを環境変数から取得
    webhook_url = os.getenv(webhook_url_env)
    if not webhook_url:
        raise ValueError(f"環境変数 {webhook_url_env} が設定されていません")
    
    # 投稿メッセージを作成
    message = f"""📰 今回のピックアップ

{entry['title']}
配信元: {entry['source']}
{entry['link']}"""
    
    # Discord Webhook に投稿
    payload = {
        'content': message,
        'username': username
    }
    
    try:
        response = requests.post(
            webhook_url,
            json=payload,
            timeout=REQUEST_TIMEOUT
        )
        response.raise_for_status()
        logger.info("Discord投稿成功")
    
    except requests.exceptions.RequestException as e:
        logger.error(f"Discord投稿失敗: {e}")
        raise


def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    """Lambda関数のメインハンドラ"""
    logger.info("Lambda関数開始")
    
    try:
        # 設定読み込み
        config = load_config()
        
        # RSS記事収集
        entries = collect_entries(config)
        
        if not entries:
            logger.info("投稿可能な記事が見つかりませんでした")
            return {
                'statusCode': 200,
                'body': json.dumps('投稿可能な記事がありませんでした')
            }
        
        # ランダム選択
        selected_entry = pick_random_entry(entries)
        if not selected_entry:
            logger.info("記事の選択に失敗しました")
            return {
                'statusCode': 200,
                'body': json.dumps('記事の選択に失敗しました')
            }
        
        # Discord投稿
        post_to_discord(selected_entry, config)
        
        logger.info("Lambda関数正常終了")
        return {
            'statusCode': 200,
            'body': json.dumps('記事を正常に投稿しました')
        }
    
    except Exception as e:
        logger.error(f"Lambda関数でエラーが発生: {e}")
        raise


if __name__ == "__main__":
    """ローカル実行用のエントリポイント"""
    logger.info("ローカル実行開始")
    
    # ダミーのイベントとコンテキスト
    test_event = {}
    test_context = type('Context', (), {})()
    
    try:
        result = lambda_handler(test_event, test_context)
        logger.info(f"実行結果: {result}")
    except Exception as e:
        logger.error(f"ローカル実行でエラー: {e}")
        sys.exit(1)