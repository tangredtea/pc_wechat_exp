"""Tests for chat_filter.py — real private chat detection."""
import pytest
from chat_filter import is_real_private_chat, filter_real_private_chats


class TestIsRealPrivateChat:
    @pytest.mark.parametrize('username', [
        'wxid_abc123def456',
        'wxid_abc123_10e8',
        '+8613812345678',
        '+14155551234',
        'zhangsan2024',
        'XYiDao',
    ])
    def test_includes_real_users(self, username):
        assert is_real_private_chat(username) is True

    @pytest.mark.parametrize('username', [
        '12345678901@chatroom',
        'gh_a1b2c3d4e5f6',
        'biz_some_account',
        'filehelper',
        'newsapp',
        'mphelper',
        'unknown_abc12345',
        '12345@openim',
        'brandsessionholder',
    ])
    def test_excludes_non_private(self, username):
        assert is_real_private_chat(username) is False

    def test_group_flag_blocks_even_if_wxid_like(self):
        assert is_real_private_chat('wxid_fake', is_group=True) is False

    def test_contact_db_fallback_for_legacy_id(self):
        chats = [{'username': 'oldfriend99', 'display_name': '老友', 'is_group': False}]
        friends = {'oldfriend99'}
        out = filter_real_private_chats(chats, friend_usernames=friends)
        assert len(out) == 1

    def test_contact_db_does_not_rescue_official_account(self):
        chats = [{'username': 'gh_abc123', 'display_name': '某号', 'is_group': False}]
        friends = {'gh_abc123'}
        out = filter_real_private_chats(chats, friend_usernames=friends)
        assert len(out) == 0
