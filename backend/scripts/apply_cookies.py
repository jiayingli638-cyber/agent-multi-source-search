"""交互式写入 MediaCrawler 各平台 Cookie 到 .env。

用法：python scripts/apply_cookies.py
说明：先在浏览器登录对应平台，从开发者工具复制完整 Cookie 字符串。

平台代码沿用 MediaCrawler 的 PlatformEnum：
  xhs 小红书 | dy 抖音 | ks 快手 | bili B站 | wb 微博 | tieba 贴吧 | zhihu 知乎
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ENV_PATH = Path(__file__).resolve().parent.parent / ".env"

PLATFORMS: list[tuple[str, str, str]] = [
    ("zhihu", "知乎 (zhihu.com)", "https://www.zhihu.com"),
    ("bili", "B站 (bilibili.com)", "https://www.bilibili.com"),
    ("wb", "微博 (m.weibo.cn)", "https://m.weibo.cn"),
    ("tieba", "贴吧 (tieba.baidu.com)", "https://tieba.baidu.com"),
    ("ks", "快手 (kuaishou.com)", "https://www.kuaishou.com"),
    ("xhs", "小红书 (xiaohongshu.com)", "https://www.xiaohongshu.com"),
    ("dy", "抖音 (douyin.com)", "https://www.douyin.com"),
    ("xiaoheihe", "小黑盒 (xiaoheihe.cn)", "https://www.xiaoheihe.cn"),
]


def upsert(env_text: str, key: str, value: str) -> str:
    pattern = re.compile(rf"^{re.escape(key)}=.*$", re.M)
    line = f"{key}={value}"
    if pattern.search(env_text):
        return pattern.sub(line, env_text)
    return env_text.rstrip("\n") + "\n" + line + "\n"


def main() -> None:
    if not ENV_PATH.exists():
        print(f"未找到 {ENV_PATH}，请先复制 .env.example 为 .env")
        return

    text = ENV_PATH.read_text(encoding="utf-8")
    print("=" * 66)
    print(" MediaCrawler / 小黑盒 Cookie 配置助手")
    print("=" * 66)
    print(" 获取方式：浏览器登录平台 → F12 → Network → 刷新 →")
    print("           点任一请求 → Request Headers → 复制 Cookie 冒号后的内容")
    print(" 直接回车 = 跳过该平台\n")

    written: list[str] = []
    for key, label, url in PLATFORMS:
        try:
            raw = input(f"{label:32s} Cookie: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n已中断。")
            break
        if not raw:
            continue
        if key == "xiaoheihe":
            text = upsert(text, "XIAOHEIHE_COOKIE", raw)
        else:
            text = upsert(text, f"MEDIACRAWLER_COOKIE_{key.upper()}", raw)
        written.append(key)

    ENV_PATH.write_text(text, encoding="utf-8")
    print(f"\n已更新 {ENV_PATH}")
    if written:
        print("本次写入：" + ", ".join(written))
        print("\n提示：确认 MEDIACRAWLER_PLATFORMS 里包含这些平台代码，否则不会被调度。")
    else:
        print("未写入任何 Cookie。")


if __name__ == "__main__":
    sys.exit(main())
