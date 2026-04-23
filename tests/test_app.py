"""
RSS Discord Bot のシンプルなテストコード
"""
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch, mock_open

# テスト対象のモジュールをインポート
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
import app


class TestRssDiscordBot(unittest.TestCase):
    """RSS Discord Bot のテストクラス"""
    
    def setUp(self):
        """各テストの前準備"""
        self.sample_config = {
            'rss_urls': [
                'https://example.com/rss1',
                'https://example.com/rss2'
            ],
            'discord': {
                'webhook_url_env': 'DISCORD_WEBHOOK_URL',
                'username': 'Test Bot'
            },
            'collect': {
                'max_entries_per_feed': 5
            }
        }
        
        self.sample_entries = [
            {
                'title': 'テスト記事1',
                'link': 'https://example.com/article1',
                'source': 'テストフィード1'
            },
            {
                'title': 'テスト記事2', 
                'link': 'https://example.com/article2',
                'source': 'テストフィード2'
            }
        ]

    def test_load_config_success(self):
        """設定ファイルの正常読み込みテスト"""
        config_yaml = """
rss_urls:
  - https://example.com/rss
discord:
  webhook_url_env: DISCORD_WEBHOOK_URL
  username: Test Bot
collect:
  max_entries_per_feed: 5
"""
        
        with patch('builtins.open', mock_open(read_data=config_yaml)):
            with patch.object(Path, 'exists', return_value=True):
                config = app.load_config()
                
                self.assertIn('rss_urls', config)
                self.assertIn('discord', config)
                self.assertIn('collect', config)
                self.assertEqual(config['collect']['max_entries_per_feed'], 5)

    def test_load_config_missing_file(self):
        """設定ファイルが存在しない場合のテスト"""
        with patch.object(Path, 'exists', return_value=False):
            with self.assertRaises(FileNotFoundError):
                app.load_config()

    def test_load_config_missing_required_key(self):
        """必須項目が欠けている場合のテスト"""
        incomplete_yaml = """
rss_urls:
  - https://example.com/rss
# discord キーが欠けている
collect:
  max_entries_per_feed: 5
"""
        
        with patch('builtins.open', mock_open(read_data=incomplete_yaml)):
            with patch.object(Path, 'exists', return_value=True):
                with self.assertRaises(ValueError) as cm:
                    app.load_config()
                self.assertIn('discord', str(cm.exception))

    def test_pick_random_entry_success(self):
        """記事のランダム選択（正常）テスト"""
        with patch('random.choice', return_value=self.sample_entries[0]):
            result = app.pick_random_entry(self.sample_entries)
            self.assertEqual(result, self.sample_entries[0])

    def test_pick_random_entry_empty(self):
        """記事のランダム選択（空リスト）テスト"""
        result = app.pick_random_entry([])
        self.assertIsNone(result)

    @patch('requests.post')
    def test_post_to_discord_success(self, mock_post):
        """Discord投稿成功のテスト"""
        # 環境変数をモック
        with patch.dict(os.environ, {'DISCORD_WEBHOOK_URL': 'https://discord.com/api/webhooks/test'}):
            # requests.postが成功するようにモック
            mock_response = Mock()
            mock_response.raise_for_status.return_value = None
            mock_post.return_value = mock_response
            
            # テスト実行
            entry = self.sample_entries[0]
            app.post_to_discord(entry, self.sample_config)
            
            # 呼び出しが正しいか確認
            mock_post.assert_called_once()
            call_args = mock_post.call_args
            self.assertIn('json', call_args.kwargs)
            self.assertIn('timeout', call_args.kwargs)
            
            # 投稿内容の確認
            payload = call_args.kwargs['json']
            self.assertIn('content', payload)
            self.assertIn('username', payload)
            self.assertEqual(payload['username'], 'Test Bot')

    def test_post_to_discord_missing_env(self):
        """Discord投稿時の環境変数未設定テスト"""
        # 環境変数を削除
        with patch.dict(os.environ, {}, clear=True):
            entry = self.sample_entries[0]
            with self.assertRaises(ValueError) as cm:
                app.post_to_discord(entry, self.sample_config)
            self.assertIn('DISCORD_WEBHOOK_URL', str(cm.exception))

    @patch('feedparser.parse')
    def test_collect_entries_success(self, mock_parse):
        """RSS記事収集成功のテスト"""
        # feedparserの戻り値をモック
        mock_feed = Mock()
        mock_feed.feed.title = 'テストフィード'
        mock_feed.bozo = False
        mock_feed.bozo_exception = None
        
        # エントリをモック
        mock_entry1 = Mock()
        mock_entry1.title = 'テスト記事1'
        mock_entry1.link = 'https://example.com/1'
        
        mock_entry2 = Mock()
        mock_entry2.title = 'テスト記事2'
        mock_entry2.link = 'https://example.com/2'
        
        mock_feed.entries = [mock_entry1, mock_entry2]
        mock_parse.return_value = mock_feed
        
        # テスト実行
        entries = app.collect_entries(self.sample_config)
        
        # 結果確認
        self.assertEqual(len(entries), 4)  # 2つのRSS × 2記事
        self.assertEqual(entries[0]['title'], 'テスト記事1')
        self.assertEqual(entries[0]['source'], 'テストフィード')

    @patch('feedparser.parse')
    def test_collect_entries_with_failures(self, mock_parse):
        """RSS収集時の一部失敗テスト"""
        # 1つ目は成功、2つ目は失敗
        def side_effect(url):
            if 'rss1' in url:
                mock_feed = Mock()
                mock_feed.feed.title = 'テストフィード1'
                mock_feed.bozo = False
                mock_feed.bozo_exception = None
                
                mock_entry = Mock()
                mock_entry.title = 'テスト記事1'
                mock_entry.link = 'https://example.com/1'
                mock_feed.entries = [mock_entry]
                return mock_feed
            else:
                raise Exception("RSS取得失敗")
        
        mock_parse.side_effect = side_effect
        
        # テスト実行
        entries = app.collect_entries(self.sample_config)
        
        # 結果確認（失敗したRSSがあっても、成功したものは取得される）
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['title'], 'テスト記事1')

    @patch('app.post_to_discord')
    @patch('app.pick_random_entry')
    @patch('app.collect_entries')
    @patch('app.load_config')
    def test_lambda_handler_success(self, mock_load_config, 
                                   mock_collect, mock_pick, mock_post):
        """Lambda関数の正常実行テスト"""
        # モックの設定
        mock_load_config.return_value = self.sample_config
        mock_collect.return_value = self.sample_entries
        mock_pick.return_value = self.sample_entries[0]
        mock_post.return_value = None
        
        # テスト実行
        result = app.lambda_handler({}, {})
        
        # 結果確認
        self.assertEqual(result['statusCode'], 200)
        body_text = json.loads(result['body'])
        self.assertIn('正常に投稿しました', body_text)
        
        # 各関数が呼ばれたか確認
        mock_load_config.assert_called_once()
        mock_collect.assert_called_once()
        mock_pick.assert_called_once()
        mock_post.assert_called_once()

    @patch('app.collect_entries')
    @patch('app.load_config')
    def test_lambda_handler_no_entries(self, mock_load_config, mock_collect):
        """Lambda関数の記事なし実行テスト"""
        # モックの設定
        mock_load_config.return_value = self.sample_config
        mock_collect.return_value = []  # 記事なし
        
        # テスト実行
        result = app.lambda_handler({}, {})
        
        # 結果確認
        self.assertEqual(result['statusCode'], 200)
        body_text = json.loads(result['body'])
        self.assertIn('記事がありませんでした', body_text)


if __name__ == '__main__':
    # テスト実行
    unittest.main(verbosity=2)