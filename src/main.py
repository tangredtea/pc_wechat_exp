"""
WeChat EXP — 便携式微信聊天记录导出分析工具
交互式菜单 + 命令行模式，双击即可使用。
"""
import os
import sys
import time
import argparse
from datetime import datetime, timedelta

# Ensure src directory is on path for imports
BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

from constants import TZ

# Output directory (relative to tool directory)
OUTPUT = os.path.join(BASE, "..", "output")
KEYS_FILE = os.path.join(OUTPUT, "all_keys.json")
DECRYPTED = os.path.join(OUTPUT, "decrypted")
EXPORT_DIR = os.path.join(BASE, "..", "exp")
WORDCLOUD_DIR = os.path.join(OUTPUT, "wordcloud")
REPORT_FILE = os.path.join(OUTPUT, "report.html")
EMPLOYEE_EXPORT_DIR = os.path.join(OUTPUT, "employee_export")


def clear_screen():
    os.system('cls' if os.name == 'nt' else 'clear')


def print_header():
    clear_screen()
    print("""
╔══════════════════════════════════════════╗
║     WeChat 聊天记录导出分析工具 v1.0      ║
║     支持微信 4.x · Windows 10/11         ║
╠══════════════════════════════════════════╣
║                                          ║
║  [1] 一键全流程（推荐首次使用）            ║
║      提取密钥 → 解密 → 导出最近30天聊天    ║
║                                          ║
║  [2] 仅提取密钥                          ║
║  [3] 仅解密数据库                        ║
║  [4] 导出聊天记录（按条件）               ║
║  [5] 员工批量导出（需员工 Excel）          ║
║  [6] 词云分析（指定聊天/群聊）            ║
║  [7] 生成 HTML 综合报告                  ║
║  [0] 退出                                ║
║                                          ║
╚══════════════════════════════════════════╝""")
    print()


def progress_bar(current, total, width=30):
    """文本进度条"""
    pct = current / total if total else 0
    filled = int(width * pct)
    bar = "█" * filled + "░" * (width - filled)
    return f"[{bar}] {pct * 100:.0f}%"


def step_header(title):
    """Print a step header"""
    print(f"\n{'━' * 3} {title} {'━' * (60 - len(title) - 5)}")


def detect_wechat():
    """Auto-detect WeChat data directory."""
    from utils import find_wechat_data_dir, is_wechat_running
    print("检测微信...", end=" ")

    if not is_wechat_running():
        print("Weixin.exe 未运行!")
        print("\n请先启动微信并登录，然后重试。")
        input("\n按 Enter 返回主菜单...")
        return None

    print("已运行")
    print("搜索微信数据目录...", end=" ")
    db_dir = find_wechat_data_dir()
    if db_dir:
        print(f"找到")
        print(f"  {db_dir}")
    else:
        print("未自动检测到!")
        print()
        print("  请按以下步骤手动查找:")
        print("  1. 打开微信，点击左下角「三」→「设置」")
        print("  2. 选择「文件管理」→ 查看「文件目录」")
        print("  3. 进入该目录，找到 xwechat_files\\<微信号>\\db_storage")
        print()
        manual = input("  请粘贴 db_storage 完整路径: ").strip().strip('"')
        if manual and os.path.isdir(manual):
            db_dir = manual
        else:
            print(f"  路径无效或不存在: {manual}")
            input("\n按 Enter 返回主菜单...")
            return None
    return db_dir


def menu_1_auto():
    """一键全流程"""
    db_dir = detect_wechat()
    if not db_dir:
        return

    # Step 1: Extract keys
    step_header("第1步: 提取密钥")
    from key_scan import run_key_scan
    try:
        key_map = run_key_scan(db_dir, KEYS_FILE,
                               print_fn=lambda x: print(f"  {x}"),
                               progress_fn=lambda p, m: print(
                                   f"  {progress_bar(p, 100)} {m}"))
        print(f"  ✓ 找到 {len(key_map)} 个密钥")
    except RuntimeError as e:
        print(f"  ✗ 密钥提取失败: {e}")
        input("\n按 Enter 返回主菜单...")
        return
    except Exception as e:
        print(f"  ✗ 发生错误: {e}")
        input("\n按 Enter 返回主菜单...")
        return

    # Step 2: Decrypt
    step_header("第2步: 解密数据库")
    from decrypt import run_decrypt
    try:
        s, f, sk = run_decrypt(KEYS_FILE, db_dir, DECRYPTED,
                               print_fn=lambda x: print(f"  {x}"),
                               progress_fn=lambda p, m: print(
                                   f"  {progress_bar(p, 100)} {m}"))
        print(f"  ✓ 解密完成: {s}成功/{f}失败/{sk}跳过")
    except Exception as e:
        print(f"  ✗ 解密失败: {e}")
        input("\n按 Enter 返回主菜单...")
        return

    # Step 3: Export recent 30 days
    step_header("第3步: 导出最近30天聊天记录")
    try:
        days_str = input("  导出最近多少天? (默认30): ").strip()
        days = int(days_str) if days_str.isdigit() else 30
    except (EOFError, KeyboardInterrupt):
        return

    end_ts = int(datetime.now(TZ).replace(hour=23, minute=59, second=59).timestamp())
    start_ts = int((datetime.now(TZ) - timedelta(days=days)).replace(
        hour=0, minute=0, second=0).timestamp())

    from chat_export import export_all_contacts
    results = export_all_contacts(DECRYPTED, EXPORT_DIR, start_ts, end_ts,
                                  print_fn=lambda x: print(f"  {x}"),
                                  progress_fn=lambda p, m: print(
                                      f"  {progress_bar(p, 100)} {m}"))
    print(f"\n  ✓ 导出完成: {len(results)} 人 / {sum(r[1] for r in results)} 条消息")
    print(f"  输出目录: {EXPORT_DIR}")

    input("\n按 Enter 返回主菜单...")


def menu_2_keys():
    """仅提取密钥"""
    db_dir = detect_wechat()
    if not db_dir:
        return
    from key_scan import run_key_scan
    try:
        run_key_scan(db_dir, KEYS_FILE,
                     print_fn=lambda x: print(f"  {x}"),
                     progress_fn=lambda p, m: print(f"  {progress_bar(p, 100)} {m}"))
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    input("\n按 Enter 返回主菜单...")


def menu_3_decrypt():
    """仅解密"""
    db_dir = detect_wechat()
    if not db_dir:
        return
    if not os.path.exists(KEYS_FILE):
        print(f"  ✗ 密钥文件不存在: {KEYS_FILE}")
        print("  请先执行 [2] 提取密钥")
        input("\n按 Enter 返回主菜单...")
        return
    from decrypt import run_decrypt
    try:
        run_decrypt(KEYS_FILE, db_dir, DECRYPTED,
                    print_fn=lambda x: print(f"  {x}"),
                    progress_fn=lambda p, m: print(f"  {progress_bar(p, 100)} {m}"))
    except Exception as e:
        print(f"  ✗ 错误: {e}")
    input("\n按 Enter 返回主菜单...")


def menu_4_export():
    """导出聊天记录（按条件）"""
    if not os.path.isdir(DECRYPTED):
        print("  ✗ 解密目录不存在，请先执行 [3] 解密数据库")
        input("\n按 Enter 返回主菜单...")
        return

    print("\n导出条件设置:")
    name_input = input("  联系人: [全部/a] 或输入姓名关键词 > ").strip()
    days_input = input("  时间范围: 最近 [30] 天 > ").strip()
    days = int(days_input) if days_input.isdigit() else 30
    kw = input("  关键词过滤: [无] > ").strip()
    dir_input = input(f"  输出目录: [{EXPORT_DIR}] > ").strip()

    name_filter = None if name_input.lower() in ('', 'a', '全部') else name_input
    out_dir = dir_input if dir_input else EXPORT_DIR

    end_ts = int(datetime.now(TZ).replace(hour=23, minute=59, second=59).timestamp())
    start_ts = int((datetime.now(TZ) - timedelta(days=days)).replace(
        hour=0, minute=0, second=0).timestamp())

    from chat_export import export_all_contacts
    results = export_all_contacts(DECRYPTED, out_dir, start_ts, end_ts,
                                  keyword=kw if kw else None,
                                  name_filter=name_filter,
                                  print_fn=lambda x: print(f"  {x}"),
                                  progress_fn=lambda p, m: print(
                                      f"  {progress_bar(p, 100)} {m}"))

    print(f"\n  ✓ 导出完成: {len(results)} 人 / {sum(r[1] for r in results)} 条消息")
    print(f"  输出目录: {out_dir}")
    input("\n按 Enter 返回主菜单...")


def menu_5_employee():
    """员工批量导出"""
    if not os.path.isdir(DECRYPTED):
        print("  ✗ 解密目录不存在，请先执行 [3] 解密数据库")
        input("\n按 Enter 返回主菜单...")
        return

    # Auto-detect Excel files
    search_paths = [BASE, os.path.join(BASE, ".."), os.getcwd()]
    excel_path = None
    for sp in search_paths:
        for f in os.listdir(sp):
            if f.endswith('.xlsx') and ('员工' in f or 'employee' in f.lower()):
                excel_path = os.path.join(sp, f)
                break
        if excel_path:
            break

    if not excel_path:
        excel_path = input("  员工 Excel 文件路径: ").strip()
        if not excel_path or not os.path.exists(excel_path):
            print("  ✗ 未找到员工 Excel 文件")
            input("\n按 Enter 返回主菜单...")
            return

    print(f"  使用: {os.path.basename(excel_path)}")

    days_input = input("  时间范围: 最近 [10] 天 > ").strip()
    days = int(days_input) if days_input.isdigit() else 10
    kw = input("  关键词过滤: [无] > ").strip()
    min_score_input = input("  最低匹配度 [30]: ").strip()
    min_score = int(min_score_input) if min_score_input.isdigit() else 30

    end_ts = int(datetime.now(TZ).replace(hour=23, minute=59, second=59).timestamp())
    start_ts = int((datetime.now(TZ) - timedelta(days=days)).replace(
        hour=0, minute=0, second=0).timestamp())

    from employee_match import run_employee_export
    run_employee_export(DECRYPTED, excel_path, EMPLOYEE_EXPORT_DIR,
                        start_ts, end_ts, keyword=kw if kw else None,
                        min_score=min_score,
                        print_fn=lambda x: print(f"  {x}"),
                        progress_fn=lambda p, m: print(f"  {progress_bar(p, 100)} {m}"))

    print(f"  输出目录: {EMPLOYEE_EXPORT_DIR}")
    input("\n按 Enter 返回主菜单...")


def menu_6_wordcloud():
    """词云分析"""
    if not os.path.isdir(DECRYPTED):
        print("  ✗ 解密目录不存在，请先执行 [3] 解密数据库")
        input("\n按 Enter 返回主菜单...")
        return

    print("""
选择分析目标:
  [1] 全局词云
  [2] 指定群聊
  [3] 指定联系人
""")
    choice = input("> ").strip()

    chat_info = None
    if choice == "2":
        kw = input("  搜索群聊名称: ").strip()
        from chat_list import list_chats
        chats = list_chats(DECRYPTED, name_filter=kw if kw else None, min_msgs=10)
        # Filter to groups
        groups = [c for c in chats if c["is_group"]]
        if not groups:
            print("  未找到匹配的群聊")
            input("\n按 Enter 返回主菜单...")
            return
        for i, c in enumerate(groups[:20]):
            print(f"  [{i+1}] {c['display_name']} ({c['msg_count']:,}条)")
        sel = input("  选择: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(groups):
            chat_info = groups[int(sel) - 1]
        else:
            return
    elif choice == "3":
        kw = input("  搜索联系人: ").strip()
        from chat_list import list_chats
        chats = list_chats(DECRYPTED, name_filter=kw if kw else None, min_msgs=5)
        for i, c in enumerate(chats[:20]):
            gtag = "[群]" if c["is_group"] else "[人]"
            print(f"  [{i+1}] {gtag} {c['display_name']} ({c['msg_count']:,}条)")
        sel = input("  选择: ").strip()
        if sel.isdigit() and 1 <= int(sel) <= len(chats):
            chat_info = chats[int(sel) - 1]
        else:
            return

    # Time period selection
    days_input = input("  分析时间范围: 最近 [30] 天 (0=全部) > ").strip()
    start_ts = None
    end_ts = None
    if days_input == "":
        days = 30
    elif days_input == "0":
        days = 0
    else:
        try:
            days = int(days_input)
        except (EOFError, KeyboardInterrupt):
            return
        except ValueError:
            days = 30

    if days > 0:
        end_ts = int(datetime.now(TZ).replace(hour=23, minute=59, second=59).timestamp())
        start_ts = int((datetime.now(TZ) - timedelta(days=days)).replace(
            hour=0, minute=0, second=0).timestamp())

    from wordcloud_gen import generate_wordcloud
    out = generate_wordcloud(DECRYPTED, chat_info=chat_info,
                             start_ts=start_ts, end_ts=end_ts,
                             print_fn=lambda x: print(f"  {x}"),
                             progress_fn=lambda p, m: print(f"  {progress_bar(p, 100)} {m}"))
    if out:
        print(f"\n  词云已生成: {out}")
        # Try to open in browser
        try:
            import webbrowser
            webbrowser.open(out)
        except Exception:
            pass
    input("\n按 Enter 返回主菜单...")


def menu_7_report():
    """生成 HTML 综合报告"""
    if not os.path.isdir(DECRYPTED):
        print("  ✗ 解密目录不存在，请先执行 [3] 解密数据库")
        input("\n按 Enter 返回主菜单...")
        return

    # Time period selection
    days_input = input("  分析时间范围: 最近 [30] 天 (0=全部) > ").strip()
    start_ts = None
    end_ts = None
    if days_input == "":
        days = 30
    elif days_input == "0":
        days = 0
    else:
        try:
            days = int(days_input)
        except (EOFError, KeyboardInterrupt):
            return
        except ValueError:
            days = 30

    if days > 0:
        end_ts = int(datetime.now(TZ).replace(hour=23, minute=59, second=59).timestamp())
        start_ts = int((datetime.now(TZ) - timedelta(days=days)).replace(
            hour=0, minute=0, second=0).timestamp())

    from report_gen import generate_report
    out = generate_report(DECRYPTED, REPORT_FILE,
                          start_ts=start_ts, end_ts=end_ts,
                          print_fn=lambda x: print(f"  {x}"),
                          progress_fn=lambda p, m: print(f"  {progress_bar(p, 100)} {m}"))
    if out:
        try:
            import webbrowser
            webbrowser.open(out)
        except Exception:
            pass
    input("\n按 Enter 返回主菜单...")


def interactive_menu():
    """主交互循环"""
    while True:
        print_header()
        try:
            choice = input("请选择 [0-7]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n再见!")
            break

        if choice == "1":
            menu_1_auto()
        elif choice == "2":
            menu_2_keys()
        elif choice == "3":
            menu_3_decrypt()
        elif choice == "4":
            menu_4_export()
        elif choice == "5":
            menu_5_employee()
        elif choice == "6":
            menu_6_wordcloud()
        elif choice == "7":
            menu_7_report()
        elif choice == "0":
            print("\n再见!")
            break
        else:
            print("\n无效选择，请重试")
            time.sleep(0.5)


def cmd_mode(args):
    """命令行模式"""
    from utils import find_wechat_data_dir, is_wechat_running

    # Auto-detect
    if not is_wechat_running():
        print("[ERROR] Weixin.exe 未运行，请先启动微信")
        sys.exit(1)

    db_dir = args.db_dir or find_wechat_data_dir()
    if not db_dir:
        print("[ERROR] 未找到微信数据目录，请用 --db-dir 指定")
        sys.exit(1)
    print(f"微信数据目录: {db_dir}")

    # Extract keys
    if args.keys or args.auto:
        from key_scan import run_key_scan
        run_key_scan(db_dir, KEYS_FILE)
        print("密钥提取完成")

    # Decrypt
    if args.decrypt or args.auto:
        from decrypt import run_decrypt
        run_decrypt(KEYS_FILE, db_dir, DECRYPTED)
        print("解密完成")

    # Export
    if args.export or args.auto:
        days = args.days or 30
        end_ts = int(datetime.now(TZ).replace(hour=23, minute=59, second=59).timestamp())
        start_ts = int((datetime.now(TZ) - timedelta(days=days)).replace(
            hour=0, minute=0, second=0).timestamp())

        from chat_export import export_all_contacts
        name_filter = args.name or None
        results = export_all_contacts(DECRYPTED, EXPORT_DIR, start_ts, end_ts,
                                      name_filter=name_filter,
                                      keyword=args.keyword)
        print(f"导出完成: {len(results)} 人 / {sum(r[1] for r in results)} 条消息")


def main():
    parser = argparse.ArgumentParser(description="WeChat EXP — 微信聊天记录导出分析工具")
    parser.add_argument("--auto", action="store_true", help="一键全流程")
    parser.add_argument("--keys", action="store_true", help="仅提取密钥")
    parser.add_argument("--decrypt", action="store_true", help="仅解密数据库")
    parser.add_argument("--export", action="store_true", help="导出聊天记录")
    parser.add_argument("--name", help="按姓名过滤")
    parser.add_argument("--days", type=int, help="最近N天")
    parser.add_argument("--keyword", help="关键词过滤")
    parser.add_argument("--db-dir", help="微信数据目录路径")
    parser.add_argument("--output", help="输出目录")
    args = parser.parse_args()

    # Resolve paths
    global OUTPUT, KEYS_FILE, DECRYPTED, EXPORT_DIR, WORDCLOUD_DIR, REPORT_FILE
    if args.output:
        OUTPUT = args.output
        KEYS_FILE = os.path.join(OUTPUT, "all_keys.json")
        DECRYPTED = os.path.join(OUTPUT, "decrypted")
        EXPORT_DIR = os.path.join(OUTPUT, "exp")
        WORDCLOUD_DIR = os.path.join(OUTPUT, "wordcloud")
        REPORT_FILE = os.path.join(OUTPUT, "report.html")

    has_cmd = any([args.auto, args.keys, args.decrypt, args.export])
    if has_cmd:
        cmd_mode(args)
    else:
        interactive_menu()


if __name__ == "__main__":
    main()
