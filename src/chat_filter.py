"""聊天会话过滤 — 识别真人私聊 vs 群聊/公众号/系统号。"""
import re

_PHONE_USERNAME_RE = re.compile(r'^\+\d{7,15}$')
_LEGACY_USERNAME_RE = re.compile(r'^[a-zA-Z][a-zA-Z0-9_-]{2,31}$')

_BLOCKLIST_EXACT = frozenset({
    'filehelper', 'fmessage', 'newsapp', 'weixin', 'qqmail', 'qqsafe',
    'mphelper', 'masssendapp', 'notifymessage', 'floatbottle',
    'brandsessionholder', 'weixinreminder', 'medianote', 'qmessage',
    'exmail_tool', 'lbsapp', 'linkedin_plugin', 'linkedin',
    'notification_messages', 'helper_entry', 'opencustomerservicemsg',
})

_BLOCKLIST_PREFIXES = (
    'gh_', 'biz_', 'wxid_gh_',
)


def _is_blocked_username(username: str) -> bool:
    low = (username or '').strip().lower()
    if not low:
        return True
    if low in _BLOCKLIST_EXACT:
        return True
    return any(low.startswith(p) for p in _BLOCKLIST_PREFIXES)


def is_real_private_chat(username: str, is_group: bool = False) -> bool:
    """判断是否为真人一对一私聊会话（按 username，非显示别名）。

    自定义微信号存在 contact.alias，消息库会话键仍是 username（多为 wxid_*）。
    """
    uname = (username or '').strip()
    if not uname or is_group or uname.endswith('@chatroom'):
        return False
    if uname.startswith('unknown_'):
        return False
    if _is_blocked_username(uname):
        return False
    if '@' in uname:
        return False
    if uname.startswith('wxid_'):
        return True
    if _PHONE_USERNAME_RE.match(uname):
        return True
    if _LEGACY_USERNAME_RE.match(uname):
        return True
    return False


def filter_real_private_chats(chats, friend_usernames=None):
    """保留真人私聊；friend_usernames 为 contact.db 中的 username 集合（兜底）。"""
    friends = friend_usernames or set()
    result = []
    for c in chats:
        uname = (c.get('username') or '').strip()
        is_group = bool(c.get('is_group')) or uname.endswith('@chatroom')
        if is_real_private_chat(uname, is_group):
            result.append(c)
        elif uname in friends and not is_group and not _is_blocked_username(uname) and '@' not in uname:
            result.append(c)
    return result
