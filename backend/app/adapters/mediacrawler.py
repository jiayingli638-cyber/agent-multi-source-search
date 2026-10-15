"""MediaCrawler 适配器：小红书 / 抖音 / 快手 / B站 / 微博 / 贴吧 / 知乎。

MediaCrawler（https://github.com/NanmiCoder/MediaCrawler）是一个独立的
Python 项目，本身不是 pip 库。本项目通过「子进程调用 + 结果文件解析」的方式桥接，
同时提供 remote 模式以对接你自建的服务化封装。

两种模式：
- local  : 调用 MEDIACRAWLER_HOME 下的 main.py，让 MediaCrawler 写入 JSON，
           本适配器再读取该文件。Cookie 通过 --cookies 参数传入。
- remote : 直接 POST 到 MEDIACRAWLER_SERVICE_URL，期望返回统一 JSON。

关键设计：Cookie 缺失 / 未部署 MediaCrawler 时，该平台返回明确提示，
不影响其它源，也不会让整个 Agent 失败。

CLI 参数以 MediaCrawler v0.1.0 `cmd_arg/arg.py` 为准：
  --platform {xhs,dy,ks,bili,wb,tieba,zhihu}
  --lt {qrcode,phone,cookie}
  --type {search,detail,creator}
  --keywords "关键词1,关键词2"
  --save_data_option {csv,db,json,jsonl,sqlite,excel,postgres}
  --crawler_max_notes_count N
  --cookies "<cookie 字符串>"
  --headless yes|no
输出路径：data/{platform}/json/{crawler_type}_{item_type}_{date}.json
"""
from __future__ import annotations

import asyncio
import json
import os
import shutil
import sys
from datetime import date
from pathlib import Path

from ..core.config import settings
from ..core.http_client import fetch_json
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)

# 平台代码 -> 中文名（代码为 MediaCrawler 的 PlatformEnum 取值）
PLATFORM_LABELS = {
    "xhs": "小红书",
    "dy": "抖音",
    "ks": "快手",
    "bili": "B站",
    "wb": "微博",
    "tieba": "贴吧",
    "zhihu": "知乎",
}

# 兼容旧配置中的英文全称写法
PLATFORM_ALIASES = {
    "xiaohongshu": "xhs",
    "douyin": "dy",
    "kuaishou": "ks",
    "bilibili": "bili",
    "weibo": "wb",
    "baidutieba": "tieba",
}

# 详情页 URL 模板
URL_PATTERNS = {
    "wb": "https://m.weibo.cn/detail/{id}",
    "xhs": "https://www.xiaohongshu.com/explore/{id}",
    "dy": "https://www.douyin.com/video/{id}",
    "ks": "https://www.kuaishou.com/short-video/{id}",
    "bili": "https://www.bilibili.com/video/{id}",
    "tieba": "https://tieba.baidu.com/p/{id}",
    "zhihu": "https://www.zhihu.com/question/{id}",
}


def normalize_platform(raw: str) -> str | None:
    """把配置中的平台名归一化为 MediaCrawler 的平台代码。"""
    key = (raw or "").strip().lower()
    key = PLATFORM_ALIASES.get(key, key)
    return key if key in PLATFORM_LABELS else None


def _resolve_executable(configured: str) -> str | None:
    """解析 MediaCrawler 的 Python 解释器路径。"""
    if not configured:
        return None
    path = Path(configured)
    if path.exists():
        return str(path)
    return shutil.which(configured)


class MediaCrawlerAdapter(SourceAdapter):
    """单个社媒平台的适配器；由 build_mediacrawler_adapters() 按平台实例化。"""

    kind = SourceKind.SOCIAL_CN
    requires_credentials = True

    def __init__(self, platform: str) -> None:
        self.platform_key = platform
        self.name = f"mediacrawler_{self.platform_key}"
        self.platform = PLATFORM_LABELS.get(self.platform_key, self.platform_key)
        self.description = f"{self.platform}内容检索（经 MediaCrawler）"

    @property
    def venv_python(self) -> Path:
        """MediaCrawler uv 虚拟环境中的解释器（由 uv sync 创建）。"""
        home = Path(settings.mediacrawler_home)
        if sys.platform == "win32":
            return home / ".venv" / "Scripts" / "python.exe"
        return home / ".venv" / "bin" / "python"

    # ---------- 可用性 ----------
    def available(self) -> bool:
        """结构可用 + 具备运行条件（有 Cookie 才会被规划器选中）。

        注意：这里把「无 Cookie」视为不可用，是为了让路由层不去调度一个
        注定要等登录超时的源。前端仍能看到该源及其具体缺失原因。
        """
        if not settings.mediacrawler_enabled:
            return False
        if settings.mediacrawler_mode == "local":
            home = settings.mediacrawler_home
            if not home or not Path(home).exists():
                return False
            if not (Path(home) / "main.py").exists():
                return False
        # remote 模式由服务端负责凭证，不在此判断
        if settings.mediacrawler_mode == "local" and not self.cookie_ready:
            return False
        return True

    def unavailable_reason(self) -> str:
        if not settings.mediacrawler_enabled:
            return "MediaCrawler 已关闭（MEDIACRAWLER_ENABLED=false）"
        if settings.mediacrawler_mode == "local":
            home = settings.mediacrawler_home or "(未设置)"
            if not home or not Path(home).exists() or not (Path(home) / "main.py").exists():
                return (
                    f"未找到本地 MediaCrawler 项目（MEDIACRAWLER_HOME={home}）。"
                    "请克隆 https://github.com/NanmiCoder/MediaCrawler 并执行 uv sync 安装依赖"
                )
            if not self.cookie_ready:
                return (
                    f"{self.platform} 缺少登录 Cookie。"
                    f"请执行 backend/scripts/apply_cookies.py 写入 "
                    f"MEDIACRAWLER_COOKIE_{self.platform_key.upper()}"
                )
        return "MediaCrawler 服务不可用"

    @property
    def cookie_ready(self) -> bool:
        return bool(settings.mediacrawler_cookie(self.platform_key))

    # ---------- 检索 ----------
    async def _search(self, query: str, limit: int) -> list[Doc]:
        if settings.mediacrawler_mode == "remote":
            return await self._search_remote(query, limit)
        # 未配置 Cookie 时直接降级，避免子进程在登录等待上白耗超时时间
        if not self.cookie_ready:
            raise RuntimeError(
                f"{self.platform} 未配置 Cookie（MEDIACRAWLER_COOKIE_{self.platform_key.upper()}）。"
                "请先用 apply_cookies.py 写入登录凭证"
            )
        return await self._search_local(query, limit)

    # ---------- remote 模式 ----------
    async def _search_remote(self, query: str, limit: int) -> list[Doc]:
        data = await fetch_json(
            f"{settings.mediacrawler_service_url.rstrip('/')}/search",
            method="POST",
            json_body={"platform": self.platform_key, "keyword": query, "limit": limit},
            headers={"Content-Type": "application/json"},
        )
        items = data if isinstance(data, list) else data.get("items") or data.get("data") or []
        return [self._to_doc(item, idx) for idx, item in enumerate(items[:limit]) if isinstance(item, dict)]

    # ---------- local 模式 ----------
    async def _search_local(self, query: str, limit: int) -> list[Doc]:
        home = Path(settings.mediacrawler_home)
        python_exe = self._pick_python(home)
        if not python_exe:
            raise RuntimeError(
                "未找到可用的 Python 解释器。请先在 MediaCrawler 目录执行 `uv sync`，"
                f"或手动设置 MEDIACRAWLER_PYTHON（当前值：{settings.mediacrawler_python!r}）"
            )

        # 记录执行前的文件时间戳，用于识别本次新增的结果
        before = self._snapshot(home)

        argv = self._build_argv(home, query, limit)
        log.info("[%s] 执行：%s", self.name, " ".join(argv))

        timeout = max(float(settings.source_timeout), float(settings.mediacrawler_timeout))
        proc = await asyncio.create_subprocess_exec(
            python_exe,
            *argv,
            cwd=str(home),
            env=self._build_env(),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
        )
        try:
            stdout, _ = await asyncio.wait_for(proc.communicate(), timeout=timeout)
        except asyncio.TimeoutError:
            proc.kill()
            await proc.wait()
            raise RuntimeError(f"MediaCrawler[{self.platform}] 执行超时（>{timeout:.0f}s）") from None

        if proc.returncode != 0:
            tail = (stdout or b"").decode("utf-8", "ignore")[-800:]
            raise RuntimeError(f"MediaCrawler[{self.platform}] 退出码 {proc.returncode}：{tail}")

        return self._read_results(home, before, limit)

    def _pick_python(self, home: Path) -> str | None:
        """优先用 uv 虚拟环境里的解释器，其次用配置项。"""
        if self.venv_python.exists():
            return str(self.venv_python)
        return _resolve_executable(settings.mediacrawler_python)

    def _build_argv(self, home: Path, query: str, limit: int) -> list[str]:
        """构造 MediaCrawler 命令行参数（已对齐 v0.1.0 的真实 CLI）。"""
        argv = [
            str(home / "main.py"),
            "--platform", self.platform_key,
            "--lt", "cookie",
            "--type", "search",
            "--keywords", query,          # 统一参数名，多关键词用逗号分隔
            "--save_data_option", "json",
            "--crawler_max_notes_count", str(max(1, limit)),
            "--get_comment", "no",        # 检索场景不需要评论，显著提速
            "--get_sub_comment", "no",
            "--get_media", "no",
            "--headless", "yes",
        ]
        cookie = settings.mediacrawler_cookie(self.platform_key)
        if cookie:
            argv += ["--cookies", cookie]
        return argv

    def _build_env(self) -> dict[str, str]:
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONUTF8"] = "1"
        cookie = settings.mediacrawler_cookie(self.platform_key)
        if cookie:
            env["MEDIACRAWLER_COOKIE"] = cookie
        return env

    # ---------- 结果读取 ----------
    def _json_dir(self, home: Path) -> Path:
        if settings.mediacrawler_save_path:
            return Path(settings.mediacrawler_save_path) / self.platform_key / "json"
        return home / "data" / self.platform_key / "json"

    def _snapshot(self, home: Path) -> dict[str, float]:
        folder = self._json_dir(home)
        if not folder.exists():
            return {}
        return {
            str(f): f.stat().st_mtime
            for f in folder.glob("*.json")
            if f.is_file()
        }

    def _read_results(self, home: Path, before: dict[str, float], limit: int) -> list[Doc]:
        """读取 MediaCrawler 输出的 JSON 结果，优先取本次新写入的文件。"""
        folder = self._json_dir(home)
        if not folder.exists():
            return []

        files = [f for f in folder.glob("*.json") if f.is_file()]

        def sort_key(p: Path) -> float:
            return p.stat().st_mtime

        fresh = [f for f in files if before.get(str(f)) != f.stat().st_mtime]
        # 本次没有新文件（如当天已有结果）则退回全量按时间倒序
        pool = fresh or files
        ordered = sorted(pool, key=sort_key, reverse=True)

        docs: list[Doc] = []
        seen: set[str] = set()
        for file in ordered[:5]:
            try:
                payload = json.loads(file.read_text(encoding="utf-8", errors="ignore"))
            except Exception:  # noqa: BLE001
                continue
            items = payload if isinstance(payload, list) else payload.get("data", [])
            if not isinstance(items, list):
                continue
            for idx, item in enumerate(items):
                if not isinstance(item, dict):
                    continue
                doc = self._to_doc(item, len(docs))
                key = doc.url or doc.title
                if key and key in seen:
                    continue
                if key:
                    seen.add(key)
                docs.append(doc)
                if len(docs) >= limit:
                    return docs
        return docs

    # ---------- 归一化 ----------
    def _to_doc(self, item: dict, idx: int) -> Doc:
        """把 MediaCrawler 各平台字段统一映射为 Doc。"""
        note_id = str(
            item.get("note_id") or item.get("aweme_id") or item.get("video_id")
            or item.get("aid") or item.get("id") or item.get("article_id")
            or item.get("bvid") or item.get("mblogid") or item.get("tieba_id") or ""
        )
        title = (
            item.get("title") or item.get("note_title") or item.get("desc")
            or item.get("content") or item.get("question") or item.get("topic")
            or item.get("video_title") or ""
        )
        content = (
            item.get("desc") or item.get("content") or item.get("text")
            or item.get("question") or item.get("answer") or ""
        )
        if not content:
            content = title
        author = (
            item.get("nickname") or item.get("user_name") or item.get("author")
            or item.get("nick_name") or item.get("user_nickname") or ""
        )
        likes = (
            item.get("liked_count") or item.get("digg_count") or item.get("voteup_count")
            or item.get("like_count") or item.get("praise_num") or 0
        )
        comments = (
            item.get("comment_count") or item.get("comments_count")
            or item.get("reply_count") or item.get("total_replay_num") or 0
        )

        return Doc(
            title=str(title)[:160],
            url=self._build_url(note_id),
            snippet=str(content)[:300],
            content=str(content)[:2000],
            source=self.name,
            source_kind=self.kind,
            platform=self.platform,
            author=str(author),
            published_at=str(
                item.get("create_time") or item.get("publish_time")
                or item.get("created_at") or item.get("time") or ""
            )[:19],
            engine_rank=idx + 1,
            score=max(0.25, 1.0 - idx * 0.08),
            extras={
                "likes": likes,
                "comments": comments,
                "platform_key": self.platform_key,
            },
        )

    def _build_url(self, note_id: str) -> str:
        if not note_id:
            return ""
        return URL_PATTERNS.get(self.platform_key, "{id}").format(id=note_id)


def build_mediacrawler_adapters() -> list[MediaCrawlerAdapter]:
    """按配置的平台列表实例化适配器。"""
    raw = settings.mediacrawler_platform_list or list(PLATFORM_LABELS)
    platforms: list[str] = []
    for item in raw:
        code = normalize_platform(item)
        if code and code not in platforms:
            platforms.append(code)
    return [MediaCrawlerAdapter(p) for p in platforms]
