"""写入各平台 Cookie 到 .env —— 支持交互式与批量两种方式。

三种用法
--------
1. 交互式（在**你自己的终端**里跑，逐个粘贴）
       python scripts/apply_cookies.py

2. 从文件批量导入（非交互；Cookie 过期后重刷也用它）
       python scripts/apply_cookies.py --from-file cookies.txt

   文件格式很宽松，以下写法都认（键可用平台代码或中文名）：
       # 以 # 开头的是注释
       zhihu=完整cookie字符串
       bili: 完整cookie字符串
       小红书=完整cookie字符串

3. 查看当前各平台 Cookie 配置状态
       python scripts/apply_cookies.py --status

平台代码沿用 MediaCrawler 的 PlatformEnum：
  xhs 小红书 | dy 抖音 | ks 快手 | bili B站 | wb 微博 | tieba 贴吧 | zhihu 知乎
另外支持 xiaoheihe 小黑盒、boss BOSS直聘（可选，二者默认走浏览器模式，不必填 Cookie）。

安全提醒：cookies.txt 与 .env 均含登录凭证，已在 .gitignore 中排除，切勿提交。
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"
DEFAULT_COOKIE_FILE = Path(__file__).resolve().parent.parent / "cookies.txt"

# 按反爬难度从低到高排列，便于按顺序处理
PLATFORMS: list[tuple[str, str, str]] = [
    ("zhihu", "知乎 (zhihu.com)", "https://www.zhihu.com"),
    ("bili", "B站 (bilibili.com)", "https://www.bilibili.com"),
    ("wb", "微博 (m.weibo.cn)", "https://m.weibo.cn"),
    ("tieba", "贴吧 (tieba.baidu.com)", "https://tieba.baidu.com"),
    ("ks", "快手 (kuaishou.com)", "https://www.kuaishou.com"),
    ("xhs", "小红书 (xiaohongshu.com)", "https://www.xiaohongshu.com"),
    ("dy", "抖音 (douyin.com)", "https://www.douyin.com"),
    ("xiaoheihe", "小黑盒 (xiaoheihe.cn)", "https://www.xiaoheihe.cn"),
    ("boss", "BOSS直聘 (zhipin.com)", "https://www.zhipin.com"),
]

# 平台代码 -> .env 变量名
ENV_KEYS: dict[str, str] = {
    "xiaoheihe": "XIAOHEIHE_COOKIE",
    "boss": "BOSS_COOKIE",
}
for _code, _, _ in PLATFORMS:
    if _code not in ENV_KEYS:
        ENV_KEYS[_code] = f"MEDIACRAWLER_COOKIE_{_code.upper()}"

# 各种可能的写法 -> 规范平台代码
ALIASES: dict[str, str] = {}
for _code, _label, _ in PLATFORMS:
    ALIASES[_code] = _code
    ALIASES[f"mediacrawler_{_code}"] = _code
    # 从标签里取出中文名，例如 "知乎 (zhihu.com)" -> "知乎"
    _zh = _label.split("(")[0].strip()
    ALIASES[_zh] = _code

ALIASES.update({
    "xiaohongshu": "xhs", "小红书": "xhs", "redbook": "xhs",
    "douyin": "dy", "抖音": "dy",
    "kuaishou": "ks", "快手": "ks",
    "bilibili": "bili", "b站": "bili", "哔哩哔哩": "bili",
    "weibo": "wb", "微博": "wb",
    "baidutieba": "tieba", "贴吧": "tieba", "百度贴吧": "tieba",
    "zhihu": "zhihu", "知乎": "zhihu",
    "xiaoheihe": "xiaoheihe", "小黑盒": "xiaoheihe", "heybox": "xiaoheihe",
    "boss": "boss", "zhipin": "boss", "boss直聘": "boss", "直聘": "boss",
})

LABEL_BY_CODE = {code: label.split("(")[0].strip() for code, label, _ in PLATFORMS}


# ------------------------------------------------------------------ 工具函数
def _use_utf8_stdout() -> None:
    """避免 Windows 控制台把中文打成乱码。"""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8")  # type: ignore[union-attr]
        except Exception:
            pass


def _read_env() -> tuple[str, str]:
    """读取 .env，返回 (文本, 原行尾符)。"""
    raw = ENV_PATH.read_bytes()
    nl = "\r\n" if b"\r\n" in raw else "\n"
    try:
        text = raw.decode("utf-8")
    except UnicodeDecodeError:
        text = raw.decode("gbk", errors="replace")
    return text, nl


def _write_env(text: str, nl: str) -> None:
    """按原行尾符写回，避免整文件 diff。"""
    normalized = text.replace("\r\n", "\n")
    ENV_PATH.write_bytes(normalized.replace("\n", nl).encode("utf-8"))


def upsert(env_text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(env_text):
        return pattern.sub(lambda _m: line, env_text)
    return env_text.rstrip("\n") + "\n" + line + "\n"


def _split_kv(line: str) -> tuple[str, str] | None:
    """拆出 (键, 值)。

    取**最靠前**的分隔符，而不是按优先级找 —— 否则
    `bili: buvid3=xxx` 会被误判成键「bili: buvid3」。
    """
    best_idx, best_sep = -1, ""
    for sep in ("=", "：", ":", "＝"):
        idx = line.find(sep)
        if idx > 0 and (best_idx == -1 or idx < best_idx):
            best_idx, best_sep = idx, sep
    if best_idx == -1:
        return None
    return line[:best_idx].strip(), line[best_idx + len(best_sep):].strip()


def _mask(value: str) -> str:
    return f"{value[:12]}…{value[-6:]}" if len(value) > 24 else "***"


# ------------------------------------------------------------------ 各模式
def show_status() -> int:
    if not ENV_PATH.exists():
        print(f"未找到 {ENV_PATH}")
        return 1
    text, _ = _read_env()

    print("=" * 74)
    print(" 各平台 Cookie 配置状态")
    print("=" * 74)
    print(f"{'平台':<10} {'变量名':<32} 状态")
    print("-" * 74)

    ready = 0
    for code, _, _ in PLATFORMS:
        key = ENV_KEYS[code]
        m = re.search(rf"^{re.escape(key)}=(.*)$", text, re.M)
        value = (m.group(1).strip() if m else "")
        if value:
            ready += 1
            state = f"已配置（{len(value)} 字符）"
        else:
            state = "未配置"
        print(f"{LABEL_BY_CODE[code]:<10} {key:<32} {state}")

    print("-" * 74)
    print(f"已配置 {ready} / {len(PLATFORMS)} 个平台")
    if ready == 0:
        print("\n提示：把 Cookie 粘进 backend/cookies.txt，然后运行")
        print("      python scripts/apply_cookies.py --from-file cookies.txt")
    return 0


def import_from_file(path: Path) -> int:
    if not ENV_PATH.exists():
        print(f"未找到 {ENV_PATH}，请先复制 .env.example 为 .env")
        return 1
    if not path.exists():
        print(f"未找到 Cookie 文件：{path}")
        print("\n请新建该文件，每行一个平台，例如：")
        print("    zhihu=完整cookie字符串")
        print("    bili=完整cookie字符串")
        print("也可以直接跑交互式：python scripts/apply_cookies.py")
        return 1

    try:
        raw_text = path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raw_text = path.read_text(encoding="gbk", errors="replace")

    text, nl = _read_env()
    written: list[str] = []
    unknown: list[str] = []
    skipped = 0

    for lineno, line in enumerate(raw_text.splitlines(), 1):
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        kv = _split_kv(stripped)
        if not kv:
            unknown.append(f"第 {lineno} 行无法识别：{stripped[:40]}")
            continue
        raw_key, value = kv
        code = ALIASES.get(raw_key.lower().replace(" ", "")) or ALIASES.get(raw_key)
        if not code:
            unknown.append(f"第 {lineno} 行未知平台「{raw_key}」")
            continue
        if not value:
            skipped += 1
            continue
        text = upsert(text, ENV_KEYS[code], value)
        written.append(code)

    _write_env(text, nl)

    print("=" * 66)
    print(f" 已从 {path.name} 导入")
    print("=" * 66)
    if written:
        print("写入成功：" + "、".join(LABEL_BY_CODE[c] for c in written))
    else:
        print("没有写入任何 Cookie。")
    if skipped:
        print(f"跳过空值 {skipped} 行")
    if unknown:
        print("\n以下行被忽略：")
        for item in unknown:
            print("  · " + item)

    print(f"\n已更新 {ENV_PATH}")
    print("提示：确认 MEDIACRAWLER_PLATFORMS 包含这些平台代码，否则不会被调度。")
    return 0


def interactive() -> int:
    if not ENV_PATH.exists():
        print(f"未找到 {ENV_PATH}，请先复制 .env.example 为 .env")
        return 1

    text, nl = _read_env()
    print("=" * 66)
    print(" 各平台 Cookie 配置助手")
    print("=" * 66)
    print(" 获取方式：浏览器登录平台 → F12 → Network → 刷新 →")
    print("           点任一请求 → Request Headers → 复制 Cookie 冒号后的内容")
    print(" 直接回车 = 跳过该平台\n")

    written: list[str] = []
    for code, label, _ in PLATFORMS:
        try:
            raw = input(f"{label:32s} Cookie: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已中断。")
            break
        if not raw:
            continue
        text = upsert(text, ENV_KEYS[code], raw)
        written.append(code)

    _write_env(text, nl)
    print(f"\n已更新 {ENV_PATH}")
    if written:
        print("本次写入：" + "、".join(LABEL_BY_CODE[c] for c in written))
        print("\n提示：确认 MEDIACRAWLER_PLATFORMS 里包含这些平台代码，否则不会被调度。")
    else:
        print("未写入任何 Cookie。")
    return 0


def main() -> int:
    _use_utf8_stdout()
    parser = argparse.ArgumentParser(
        description="写入各平台 Cookie 到 .env",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--from-file", metavar="PATH", type=Path,
                        help="从文件批量导入（默认 cookies.txt）")
    parser.add_argument("--status", action="store_true",
                        help="只查看当前配置状态，不修改文件")
    args = parser.parse_args()

    if args.status:
        return show_status()
    if args.from_file is not None:
        return import_from_file(args.from_file)
    return interactive()


if __name__ == "__main__":
    sys.exit(main())
