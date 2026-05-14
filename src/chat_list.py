"""
聊天列表扫描 — 遍历解密后数据库，列出所有聊天会话并解析名称。
"""
import hashlib
import os
import re
import sqlite3
from collections import defaultdict


def scan_chats(decrypted_dir):
    """扫描所有聊天会话。
    Returns:
        chats: [{username, display_name, msg_count, is_group, tables: [{db_idx, db_path, table_name}]}]
        id_to_name: {contact_id: display_name}
        name_to_id: {username: contact_id}
    """
    contact_db = os.path.join(decrypted_dir, "contact", "contact.db")
    session_db = os.path.join(decrypted_dir, "session", "session.db")
    msg_dir = os.path.join(decrypted_dir, "message")

    # Load contacts
    id_to_name = {}
    name_to_id = {}
    if os.path.exists(contact_db):
        conn = sqlite3.connect(contact_db)
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
        finally:
            conn.close()

    # Load session summaries for group name fallback
    session_summaries = {}
    if os.path.exists(session_db):
        conn = sqlite3.connect(session_db)
        try:
            for r in conn.execute("SELECT username, summary FROM SessionTable"):
                uname, summary = r
                if uname and summary:
                    session_summaries[uname] = str(summary).strip()
        finally:
            conn.close()

    # Load chat_room owners for another fallback
    room_owners = {}
    if os.path.exists(contact_db):
        conn = sqlite3.connect(contact_db)
        try:
            for r in conn.execute("SELECT username, owner FROM chat_room"):
                uname, owner = r
                if uname and owner:
                    room_owners[uname] = str(owner).strip()
        finally:
            conn.close()

    # Scan message DBs for Msg_ tables
    msg_dbs = []
    if os.path.isdir(msg_dir):
        for f in os.listdir(msg_dir):
            m = re.match(r'message_(\d+)\.db', f)
            if m:
                msg_dbs.append((int(m.group(1)), os.path.join(msg_dir, f)))
    msg_dbs.sort(key=lambda x: x[0])

    # Build hash -> username mapping from Name2Id tables
    hash_to_username = {}
    for idx, db_path in msg_dbs:
        try:
            conn = sqlite3.connect(db_path)
            for (uname,) in conn.execute("SELECT user_name FROM Name2Id"):
                if uname:
                    h = hashlib.md5(uname.encode()).hexdigest()
                    hash_to_username[h] = uname
            conn.close()
        except Exception:
            pass

    # Collect all Msg_ tables and their message counts
    chat_info = defaultdict(lambda: {"tables": [], "total_msgs": 0})

    for idx, db_path in msg_dbs:
        try:
            conn = sqlite3.connect(db_path)
            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'Msg_%'"
            ).fetchall()
            for (tname,) in tables:
                h = tname[4:]
                uname = hash_to_username.get(h, "")
                if not uname:
                    # Try to find username from the Name2Id table
                    try:
                        r = conn.execute(
                            "SELECT user_name FROM Name2Id WHERE rowid IN "
                            "(SELECT rowid FROM Name2Id LIMIT 1)"
                        ).fetchone()
                    except Exception:
                        pass

                    if not uname:
                        uname = f"unknown_{h[:8]}"

                count = conn.execute(
                    f"SELECT COUNT(*) FROM [{tname}]"
                ).fetchone()[0]

                chat_info[uname]["tables"].append({
                    "db_idx": idx,
                    "db_path": db_path,
                    "table_name": tname,
                })
                chat_info[uname]["total_msgs"] += count
            conn.close()
        except Exception:
            pass

    # Resolve display names
    chats = []
    for uname, info in chat_info.items():
        is_group = uname.endswith("@chatroom")
        display = _resolve_display(uname, is_group, id_to_name, name_to_id,
                                   session_summaries, room_owners)
        chats.append({
            "username": uname,
            "display_name": display,
            "msg_count": info["total_msgs"],
            "is_group": is_group,
            "tables": info["tables"],
        })

    chats.sort(key=lambda x: x["msg_count"], reverse=True)
    return chats, id_to_name, name_to_id


def _resolve_display(uname, is_group, id_to_name, name_to_id,
                     session_summaries, room_owners):
    """Resolve display name for a chat username."""
    # Direct contact lookup
    if uname in name_to_id:
        cid = name_to_id[uname]
        if cid in id_to_name:
            name = id_to_name[cid]
            if name != uname:
                return name

    if not is_group:
        return uname

    # Group chat: session summary
    if uname in session_summaries:
        summary = session_summaries[uname]
        for sep in [":", "："]:
            if sep in summary:
                name_part = summary.split(sep)[0].strip()
                if name_part and len(name_part) < 60:
                    return name_part
        if len(summary) < 40:
            return summary

    # Group chat: room owner
    if uname in room_owners:
        return room_owners[uname]

    # Fallback
    short = uname[:12] + "..." if len(uname) > 12 else uname
    return f"群聊({short})"


def list_chats(decrypted_dir, name_filter=None, min_msgs=0):
    """便捷函数：列出聊天，支持名称过滤。
    Returns: filtered chats list
    """
    chats, _, _ = scan_chats(decrypted_dir)
    result = []
    for c in chats:
        if c["msg_count"] < min_msgs:
            continue
        if name_filter:
            kw = name_filter.lower()
            if kw not in c["display_name"].lower() and kw not in c["username"].lower():
                continue
        result.append(c)
    return result
