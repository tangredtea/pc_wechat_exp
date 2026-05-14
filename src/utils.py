"""
公共工具: 微信路径自动检测、联系人加载、群聊名称解析、消息DB迭代。
"""
import glob as _glob
import os
import re
import shutil
import sqlite3
import hashlib
from collections import defaultdict


def find_wechat_data_dir():
    r"""自动检测微信 db_storage 数据目录。

    检测策略 (按优先级):
      1. 解析 %APPDATA%\Tencent\xwechat\config\*.ini (微信自写配置，最可靠)
      2. 常见数据根目录 + xwechat_files\*\db_storage 定深 glob
      3. 遍历所有驱动器根目录查找 xwechat_files

    多个账号时优先选 message 目录最近修改过的 (当前活跃账号)。
    Returns: db_storage 目录路径, 或 None
    """
    # ---- 收集候选数据根目录 ----
    data_roots = []

    # 策略1: 微信 config/*.ini — 每文件一行纯文本路径 (非标准 INI)
    appdata = os.environ.get("APPDATA", "")
    config_dir = os.path.join(appdata, "Tencent", "xwechat", "config")
    if os.path.isdir(config_dir):
        for fname in os.listdir(config_dir):
            if not fname.endswith(".ini"):
                continue
            fpath = os.path.join(config_dir, fname)
            try:
                # 微信 ini 是纯文本路径，先读内容再判断
                content = None
                for enc in ("utf-8", "gbk"):
                    try:
                        with open(fpath, "r", encoding=enc) as f:
                            content = f.read(1024).strip()
                        break
                    except UnicodeDecodeError:
                        continue
                if content and os.path.isdir(content):
                    data_roots.append(content)
            except OSError:
                continue

    # 策略2: 常见父目录
    userprofile = os.environ.get("USERPROFILE", "")
    homedrive = os.environ.get("HOMEDRIVE", "C:")
    common_parents = [
        os.path.join(userprofile, "Documents"),
        homedrive + os.sep,
        "D:\\",
        "C:\\",
        "E:\\",
        "F:\\",
    ]
    for p in common_parents:
        if os.path.isdir(p) and p not in data_roots:
            data_roots.append(p)

    # 策略3: 补充所有存在的驱动器根目录 (C:\ D:\ ...)
    try:
        import ctypes
        drives_bitmask = ctypes.windll.kernel32.GetLogicalDrives()
        for i in range(26):
            if drives_bitmask & (1 << i):
                root = chr(ord('A') + i) + ":\\"
                if os.path.isdir(root) and root not in data_roots:
                    data_roots.append(root)
    except Exception:
        pass

    # ---- 在每个数据根下搜索 xwechat_files/*/db_storage ----
    import glob as _glob
    candidates = []
    seen = set()

    for root in data_roots:
        # WeChat 4.x 结构固定: <root>/xwechat_files/<wxid>/db_storage
        pattern = os.path.join(root, "xwechat_files", "*", "db_storage")
        try:
            for match in _glob.glob(pattern):
                # glob 已保证深度，只需验证是目录
                norm = os.path.normcase(os.path.normpath(match))
                if norm not in seen and os.path.isdir(match):
                    seen.add(norm)
                    candidates.append(match)
        except Exception:
            continue

    if not candidates:
        return None

    # ---- 多个账号时选最近活跃的 (message 目录 mtime 最大) ----
    def _activity_score(db_storage_path):
        msg_dir = os.path.join(db_storage_path, "message")
        try:
            return os.path.getmtime(msg_dir) if os.path.isdir(msg_dir) else 0
        except OSError:
            return 0

    candidates.sort(key=_activity_score, reverse=True)
    return candidates[0]


def is_wechat_running():
    """检查 Weixin.exe 是否在运行。"""
    import subprocess
    try:
        r = subprocess.run(
            ["tasklist", "/FI", "IMAGENAME eq Weixin.exe", "/FO", "CSV", "/NH"],
            capture_output=True, text=True, timeout=10
        )
        return "Weixin.exe" in r.stdout
    except Exception:
        return False


def load_contacts(decrypted_dir):
    """加载联系人映射。
    Returns:
        id_to_name: {contact_id: display_name}
        name_to_id: {username: contact_id}
        usernames: set of all usernames
    """
    id_to_name = {}
    name_to_id = {}
    usernames = set()

    db_path = os.path.join(decrypted_dir, "contact", "contact.db")
    if not os.path.exists(db_path):
        return id_to_name, name_to_id, usernames

    conn = sqlite3.connect(db_path)
    try:
        for r in conn.execute(
            "SELECT id, username, remark, nick_name, alias FROM contact"
        ):
            cid, uname, remark, nick, alias = r
            uname = (uname or "").strip()
            display = (remark or nick or alias or uname).strip()
            if cid and display:
                id_to_name[cid] = display
            if uname:
                name_to_id[uname] = cid
                usernames.add(uname)
    finally:
        conn.close()
    return id_to_name, name_to_id, usernames


def resolve_group_name(username, decrypted_dir, id_to_name=None, name_to_id=None):
    """三级解析群聊名称。

    1. contact.db: COALESCE(remark, nick_name, alias)
    2. session.db: SessionTable.summary 提取显示名
    3. contact.db: chat_room 表 owner 字段
    4. 降级: "群聊(XXXX)"

    Returns: (display_name, source)  如 ("北京B组", "contact_remark")
    """
    if not username.endswith("@chatroom"):
        return (username, "self")

    # Level 1: contact.db
    contact_db = os.path.join(decrypted_dir, "contact", "contact.db")
    if os.path.exists(contact_db):
        conn = sqlite3.connect(contact_db)
        try:
            row = conn.execute(
                "SELECT COALESCE(remark, nick_name, alias) FROM contact WHERE username=?",
                (username,)
            ).fetchone()
            if row and row[0] and row[0].strip() and row[0].strip() != username:
                conn.close()
                return (row[0].strip(), "contact")
            conn.close()
        except:
            conn.close()

    # Level 2: session.db summary
    session_db = os.path.join(decrypted_dir, "session", "session.db")
    if os.path.exists(session_db):
        conn = sqlite3.connect(session_db)
        try:
            row = conn.execute(
                "SELECT summary FROM SessionTable WHERE username=?",
                (username,)
            ).fetchone()
            if row and row[0]:
                summary = str(row[0]).strip()
                # 格式: "显示名:最后一条消息" 或 "显示名：最后一条消息"
                for sep in [":", "："]:
                    if sep in summary:
                        name_part = summary.split(sep)[0].strip()
                        if name_part and len(name_part) < 60:
                            conn.close()
                            return (name_part, "session_summary")
                # 尝试直接使用 summary (可能整个就是群名)
                if len(summary) < 40:
                    conn.close()
                    return (summary, "session_summary")
            conn.close()
        except:
            conn.close()

    # Level 3: chat_room 表
    if os.path.exists(contact_db):
        conn = sqlite3.connect(contact_db)
        try:
            row = conn.execute(
                "SELECT owner FROM chat_room WHERE username=?",
                (username,)
            ).fetchone()
            if row and row[0] and str(row[0]).strip():
                conn.close()
                return (str(row[0]).strip(), "chat_room_owner")
            conn.close()
        except:
            conn.close()

    # Level 4: 降级
    short_id = username[:12] + "..." if len(username) > 12 else username
    return (f"群聊({short_id})", "fallback")


def iter_message_dbs(decrypted_dir):
    """迭代解密后的 message_N.db 文件。"""
    msg_dir = os.path.join(decrypted_dir, "message")
    dbs = []
    if not os.path.isdir(msg_dir):
        return dbs
    for f in os.listdir(msg_dir):
        m = re.match(r'message_(\d+)\.db', f)
        if m:
            dbs.append((int(m.group(1)), os.path.join(msg_dir, f)))
    return sorted(dbs, key=lambda x: x[0])


def get_msg_table(conn, username):
    """获取指定 username 对应的 Msg_ 表是否存在于此 DB 中。"""
    h = hashlib.md5(username.encode()).hexdigest()
    tname = f"Msg_{h}"
    row = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (tname,)
    ).fetchone()
    return tname if row else None


def copy_db_if_locked(db_path):
    """如果 DB 文件被微信锁定，复制到临时目录后返回临时路径。"""
    tmp_path = None
    try:
        # 尝试以读写模式打开测试是否被锁
        f = open(db_path, 'rb')
        f.close()
        return db_path  # 未锁定
    except (PermissionError, OSError):
        import tempfile
        tmp = tempfile.NamedTemporaryFile(suffix='.db', delete=False)
        tmp_path = tmp.name
        tmp.close()
        shutil.copy2(db_path, tmp_path)
        return tmp_path


def cleanup_tmp(tmp_path):
    """清理临时文件。"""
    import tempfile
    if tmp_path and tmp_path.startswith(tempfile.gettempdir()):
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
