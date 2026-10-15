"""BOSS 直聘（zhipin.com）适配器。

BOSS 直聘是国内主流招聘平台。它的职位检索接口是内部 API：

    GET https://www.zhipin.com/wapi/zpgeek/search/joblist.json

关于「字体反爬」：前端展示的薪资数字用自定义动态字体渲染（每次访问都不同），
解析 HTML 或解析 woff 都走不通。但该 API 的 `salaryDesc` 字段本身就是**明文**
（如 `30-60K·15薪`）—— 字体混淆只是前端渲染层。所以正确做法是直接调 API，
而不是去抓 DOM。

门槛：接口有 Cookie 校验 + `__zp_stoken__` 风控参数，必须**在已登录的
浏览器页面上下文里**发起请求才通得过。这与小黑盒的情况同构，因此复用同一套
「浏览器桥接」方案：

- **browser**（默认，推荐）：Playwright 打开 BOSS 页面 → 在页面内 fetch 接口
  → 自动带上真实 Cookie / stoken / UA / TLS 指纹。首次扫码登录一次，
  登录态持久化在 XIAOHEIHE_USER_DATA_DIR 同级的 boss-profile 目录。

- **api**（轻量）：httpx 直连，需手工粘贴完整 Cookie（含 `__zp_stoken__`）。

经验证的请求参数（来自公开的接口分析资料）：
    scene=1  query=<关键词>  city=<城市代码>  page=1  pageSize=30
    可选筛选：experience / payType / partTime / degree / industry / scale / stage / position / jobType
城市代码为 9 位编码，如 北京 101010100、上海 101020100、广州 101280100、
深圳 101280600、杭州 101210100；留空则不限城市。

仅用于个人信息检索研究，请遵守目标网站的使用条款，勿大规模抓取。
"""
from __future__ import annotations

import asyncio
import urllib.parse
from pathlib import Path
from typing import Any

from ..core.config import settings
from ..core.http_client import fetch_json
from ..core.logging_utils import get_logger
from ..core.models import Doc, SourceKind
from .base import SourceAdapter

log = get_logger(__name__)

WEB_ORIGIN = "https://www.zhipin.com"
API_PATH = "/wapi/zpgeek/search/joblist.json"

BROWSER_UA = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36"
)

# 常用城市代码（9 位）。留空 = 全国。
CITY_CODES: dict[str, str] = {
    "全国": "",
    "北京": "101010100",
    "上海": "101020100",
    "广州": "101280100",
    "深圳": "101280600",
    "杭州": "101210100",
    "成都": "101270100",
    "武汉": "101200100",
    "南京": "101190100",
    "西安": "101110100",
    "苏州": "101190400",
    "长沙": "101250100",
    "郑州": "101180100",
    "重庆": "101040100",
    "天津": "101030100",
    "青岛": "101120200",
    "合肥": "101220100",
    "厦门": "101230200",
    "福州": "101230100",
    "济南": "101120100",
    "大连": "101070200",
    "沈阳": "101070100",
    "宁波": "101210400",
    "东莞": "101281600",
    "佛山": "101280800",
    "无锡": "101190200",
    "香港": "101320100",
}

# 在查询里出现这些词时用于推断城市
_CITY_HINTS = tuple(CITY_CODES.keys())


class BossZhipinAdapter(SourceAdapter):
    """BOSS 直聘职位检索。"""

    name = "boss_zhipin"
    kind = SourceKind.RECRUIT
    platform = "BOSS直聘"
    requires_credentials = False  # browser 模式可交互登录
    description = "BOSS直聘职位检索（岗位/公司/薪资/技能标签）"

    def __init__(self) -> None:
        self._browser_lock = asyncio.Lock()

    # ---------- 可用性 ----------
    def available(self) -> bool:
        return settings.boss_enabled

    def unavailable_reason(self) -> str:
        return "BOSS直聘源已关闭（BOSS_ENABLED=false）"

    @property
    def mode(self) -> str:
        return (settings.boss_mode or "browser").strip().lower()

    # ---------- 检索 ----------
    async def _search(self, query: str, limit: int) -> list[Doc]:
        keyword, city = self._parse_query(query)
        if not keyword:
            return []

        params = self._build_params(keyword, city, page=1, page_size=min(30, max(15, limit)))

        if self.mode == "api" and settings.boss_cookie.strip():
            payload = await self._fetch_via_api(params)
        else:
            payload = await self._fetch_via_browser(params)

        docs = self._parse_jobs(payload, limit)
        if not docs:
            docs.append(self._search_entry(keyword, city, reason=self._degrade_hint()))
        return docs[:limit]

    def _degrade_hint(self) -> str:
        if self.mode == "browser":
            return "浏览器模式未获取到职位（可能未完成登录或风控拦截）"
        return "未配置 BOSS_COOKIE，接口鉴权失败"

    # ---------- 查询解析 ----------
    def _parse_query(self, query: str) -> tuple[str, str]:
        """从查询里推断关键词与城市。城市命中词会被剔除出关键词。"""
        text = query.strip()
        city_code = ""
        keyword = text

        # 显式配置的城市优先
        forced = settings.boss_city.strip()
        if forced:
            city_code = CITY_CODES.get(forced, forced if forced.isdigit() else "")

        # 从查询中识别城市词
        for name in _CITY_HINTS:
            if name and name in text and name != "全国":
                if not city_code:
                    city_code = CITY_CODES[name]
                keyword = keyword.replace(name, " ")
                break

        # 清理常见的招聘意图词，留下真正的岗位关键词
        for noise in ("招聘", "岗位", "职位", "工作", "找工作", "投递", "薪资", "待遇"):
            keyword = keyword.replace(noise, " ")
        keyword = " ".join(keyword.split()).strip()
        return (keyword or text), city_code

    def _build_params(self, keyword: str, city: str, page: int, page_size: int) -> dict[str, Any]:
        return {
            "scene": 1,
            "query": keyword,
            "city": city,
            "page": page,
            "pageSize": page_size,
            # 以下筛选位留空表示不限
            "experience": "",
            "payType": "",
            "partTime": "",
            "degree": "",
            "industry": "",
            "scale": "",
            "stage": "",
            "position": "",
            "jobType": "",
        }

    def _build_url(self, params: dict[str, Any]) -> str:
        return f"{WEB_ORIGIN}{API_PATH}?{urllib.parse.urlencode(params)}"

    # ---------- 通道 A：Playwright 浏览器桥接 ----------
    async def _fetch_via_browser(self, params: dict[str, Any]) -> dict[str, Any]:
        async with self._browser_lock:
            try:
                return await asyncio.wait_for(
                    self._browser_worker(params), timeout=settings.boss_timeout
                )
            except asyncio.TimeoutError:
                log.warning("[boss_zhipin] 浏览器模式超时")
                return {}
            except Exception as exc:  # noqa: BLE001
                log.warning("[boss_zhipin] 浏览器模式失败: %s", exc)
                return {}

    async def _browser_worker(self, params: dict[str, Any]) -> dict[str, Any]:
        from playwright.async_api import async_playwright  # 延迟导入

        user_data = Path(settings.boss_user_data_dir).expanduser()
        user_data.mkdir(parents=True, exist_ok=True)

        async with async_playwright() as p:
            ctx = await p.chromium.launch_persistent_context(
                user_data_dir=str(user_data),
                headless=settings.boss_headless,
                user_agent=BROWSER_UA,
                viewport={"width": 1440, "height": 900},
                locale="zh-CN",
                args=[
                    "--disable-blink-features=AutomationControlled",
                    "--no-sandbox",
                    "--disable-dev-shm-usage",
                ],
            )
            try:
                page = ctx.pages[0] if ctx.pages else await ctx.new_page()
                # 先进职位搜索页，让站点下发 cookie / stoken
                search_url = f"{WEB_ORIGIN}/web/geek/job?query={urllib.parse.quote(str(params['query']))}"
                await page.goto(
                    search_url,
                    wait_until="domcontentloaded",
                    timeout=int(settings.boss_timeout * 1000),
                )
                await page.wait_for_timeout(2500)

                api_url = self._build_url(params)
                payload = await page.evaluate(
                    """async (u) => {
                        try {
                            const r = await fetch(u, {
                                credentials: 'include',
                                headers: {'accept': 'application/json, text/plain, */*'}
                            });
                            const t = await r.text();
                            try { return JSON.parse(t); }
                            catch { return {code: -1, message: t.slice(0, 200)}; }
                        } catch (e) {
                            return {code: -2, message: String(e).slice(0, 200)};
                        }
                    }""",
                    api_url,
                )
                return payload if isinstance(payload, dict) else {}
            finally:
                await ctx.close()

    # ---------- 通道 B：httpx 直连 ----------
    async def _fetch_via_api(self, params: dict[str, Any]) -> dict[str, Any]:
        try:
            data = await fetch_json(self._build_url(params), headers=self._headers())
            return data if isinstance(data, dict) else {}
        except Exception as exc:  # noqa: BLE001
            log.debug("[boss_zhipin] API 请求失败: %s", exc)
            return {}

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/json, text/plain, */*",
            "Referer": f"{WEB_ORIGIN}/web/geek/job",
            "Origin": WEB_ORIGIN,
            "User-Agent": BROWSER_UA,
        }
        cookie = settings.boss_cookie.strip()
        if cookie:
            headers["Cookie"] = cookie
        return headers

    # ---------- 解析 ----------
    def _parse_jobs(self, payload: dict[str, Any], limit: int) -> list[Doc]:
        if not isinstance(payload, dict):
            return []
        # BOSS 成功返回 code=0；风控命中时 code 为 1/其他
        if payload.get("code") not in (0, None) and not payload.get("zpData"):
            log.debug("[boss_zhipin] 非成功响应 code=%s msg=%s",
                      payload.get("code"), payload.get("message"))
            return []

        zp = payload.get("zpData") or payload.get("data") or {}
        jobs = zp.get("jobList") or zp.get("jobs") or []
        if not isinstance(jobs, list):
            return []

        docs: list[Doc] = []
        for idx, job in enumerate(jobs):
            if not isinstance(job, dict):
                continue
            doc = self._to_doc(job, idx)
            if doc:
                docs.append(doc)
            if len(docs) >= limit:
                break
        return docs

    def _to_doc(self, job: dict[str, Any], idx: int) -> Doc | None:
        title = str(job.get("jobName") or job.get("jobTitle") or "").strip()
        company = str(job.get("brandName") or job.get("companyName") or "").strip()
        if not title and not company:
            return None

        salary = str(job.get("salaryDesc") or "").strip()
        city = str(job.get("cityName") or "").strip()
        district = str(job.get("areaDistrict") or "").strip()
        business = str(job.get("businessDistrict") or "").strip()
        exp = str(job.get("jobExperience") or "").strip()
        degree = str(job.get("jobDegree") or "").strip()
        boss_name = str(job.get("bossName") or "").strip()
        boss_title = str(job.get("bossTitle") or "").strip()

        labels = [str(x) for x in (job.get("jobLabels") or []) if x]
        skills = [str(x) for x in (job.get("skills") or []) if x]
        welfare = [str(x) for x in (job.get("welfareList") or []) if x]

        industry = str(job.get("brandIndustry") or "").strip()
        scale = str(job.get("brandScaleName") or "").strip()
        stage = str(job.get("brandStageName") or "").strip()

        # 职位详情 URL 需要列表接口返回的 securityId / lid 上下文
        security_id = str(job.get("securityId") or "")
        encrypt_job_id = str(job.get("encryptJobId") or job.get("jobId") or "")
        url = (
            f"{WEB_ORIGIN}/job_detail/{encrypt_job_id}.html"
            f"?securityId={urllib.parse.quote(security_id)}"
            if encrypt_job_id
            else f"{WEB_ORIGIN}/web/geek/job?query={urllib.parse.quote(title or company)}"
        )

        loc = "·".join(x for x in (city, district, business) if x)
        meta = " | ".join(
            x for x in (salary, loc, exp, degree, f"{company}({scale})" if company else "") if x
        )
        detail = "；".join(x for x in (
            f"技能：{'、'.join(skills)}" if skills else "",
            f"标签：{'、'.join(labels)}" if labels else "",
            f"福利：{'、'.join(welfare)}" if welfare else "",
            f"行业：{industry}" if industry else "",
            f"融资：{stage}" if stage else "",
            f"招聘者：{boss_name} {boss_title}".strip() if boss_name else "",
        ) if x)

        snippet = f"{meta}｜{detail}" if detail else meta

        return Doc(
            title=f"{title} - {company}" if company else title,
            url=url,
            snippet=snippet[:300],
            content=f"{meta}\n{detail}"[:2000],
            source=self.name,
            source_kind=self.kind,
            platform=self.platform,
            author=boss_name or company,
            published_at=str(job.get("lastModifyTime") or "")[:19],
            engine_rank=idx + 1,
            score=max(0.3, 0.92 - idx * 0.02),
            extras={
                "salary": salary,
                "city": city,
                "district": district,
                "company": company,
                "company_scale": scale,
                "company_stage": stage,
                "industry": industry,
                "experience": exp,
                "degree": degree,
                "skills": skills,
                "labels": labels,
                "welfare": welfare,
                "boss": f"{boss_name} {boss_title}".strip(),
                "job_id": encrypt_job_id,
                "kind": "job",
            },
        )

    # ---------- 兜底入口 ----------
    def _search_entry(self, keyword: str, city: str, reason: str = "") -> Doc:
        city_name = next((k for k, v in CITY_CODES.items() if v and v == city), "")
        url = (
            f"{WEB_ORIGIN}/web/geek/job?query={urllib.parse.quote(keyword)}"
            + (f"&city={city}" if city else "")
        )
        label = f"{city_name}" if city_name else "全国"
        note = "浏览器模式下未取到职位数据" if not reason else reason
        return Doc(
            title=f"在 BOSS直聘搜索「{keyword}」（{label}）",
            url=url,
            snippet=f"BOSS直聘职位搜索入口。{note}，此处提供可直接跳转的搜索页。",
            content="",
            source=self.name,
            source_kind=self.kind,
            platform=self.platform,
            engine_rank=99,
            score=0.2,
            extras={"kind": "search_entry", "degraded_reason": reason, "city": city},
        )
