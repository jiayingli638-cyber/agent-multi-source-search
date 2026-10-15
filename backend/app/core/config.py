"""集中式配置加载。

所有环境变量通过 pydantic-settings 读取，支持 .env 文件。
未配置的凭证不会导致启动失败，对应数据源在运行时自动降级。
"""
from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# __file__ = <backend>/app/core/config.py → parents[2] = <backend>
BACKEND_DIR = Path(__file__).resolve().parents[2]
ENV_FILE = BACKEND_DIR / ".env"


def _read_env_var(name: str) -> str:
    """从进程环境或 .env 文件读取变量（.env 优先，便于热改配置）。"""
    import os

    from dotenv import dotenv_values

    try:
        values = dotenv_values(ENV_FILE)
        value = values.get(name)
        if value:
            return str(value).strip()
    except Exception:  # noqa: BLE001
        pass
    return os.environ.get(name, "").strip()


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(ENV_FILE),
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    # ---------- 大模型 ----------
    deepseek_api_key: str = Field(default="", alias="DEEPSEEK_API_KEY")
    deepseek_base_url: str = Field(default="https://api.deepseek.com", alias="DEEPSEEK_BASE_URL")
    deepseek_model: str = Field(default="deepseek-chat", alias="DEEPSEEK_MODEL")
    deepseek_reasoner_model: str = Field(default="deepseek-reasoner", alias="DEEPSEEK_REASONER_MODEL")

    # ---------- 服务 ----------
    host: str = Field(default="0.0.0.0", alias="HOST")
    port: int = Field(default=8000, alias="PORT")
    cors_origins: str = Field(default="http://localhost:3000,http://127.0.0.1:3000", alias="CORS_ORIGINS")

    # ---------- 检索行为 ----------
    max_concurrency: int = Field(default=6, alias="MAX_CONCURRENCY")
    source_timeout: float = Field(default=20.0, alias="SOURCE_TIMEOUT")
    max_results_per_source: int = Field(default=8, alias="MAX_RESULTS_PER_SOURCE")
    enable_mock_fallback: bool = Field(default=True, alias="ENABLE_MOCK_FALLBACK")

    # ---------- Bing ----------
    bing_search_api_key: str = Field(default="", alias="BING_SEARCH_API_KEY")
    bing_search_endpoint: str = Field(
        default="https://api.bing.microsoft.com/v7.0/search", alias="BING_SEARCH_ENDPOINT"
    )
    bing_html_enabled: bool = Field(default=True, alias="BING_HTML_ENABLED")

    # ---------- Google ----------
    serper_api_key: str = Field(default="", alias="SERPER_API_KEY")
    serpapi_api_key: str = Field(default="", alias="SERPAPI_API_KEY")
    google_search_provider: str = Field(default="serper", alias="GOOGLE_SEARCH_PROVIDER")

    # ---------- Nexus ----------
    nexus_api_url: str = Field(default="https://api.crossref.org/works", alias="NEXUS_API_URL")
    nexus_api_key: str = Field(default="", alias="NEXUS_API_KEY")
    nexus_mailto: str = Field(default="", alias="NEXUS_MAILTO")

    # ---------- GitHub ----------
    github_token: str = Field(default="", alias="GITHUB_TOKEN")
    github_api_url: str = Field(default="https://api.github.com", alias="GITHUB_API_URL")

    # ---------- arXiv ----------
    arxiv_enabled: bool = Field(default=True, alias="ARXIV_ENABLED")
    arxiv_api_url: str = Field(default="http://export.arxiv.org/api/query", alias="ARXIV_API_URL")

    # ---------- MediaCrawler ----------
    mediacrawler_enabled: bool = Field(default=True, alias="MEDIACRAWLER_ENABLED")
    mediacrawler_mode: str = Field(default="local", alias="MEDIACRAWLER_MODE")
    mediacrawler_home: str = Field(default="", alias="MEDIACRAWLER_HOME")
    mediacrawler_python: str = Field(default="python", alias="MEDIACRAWLER_PYTHON")
    mediacrawler_service_url: str = Field(default="http://127.0.0.1:9000", alias="MEDIACRAWLER_SERVICE_URL")
    mediacrawler_platforms: str = Field(
        default="xhs,dy,ks,bili,wb,tieba,zhihu", alias="MEDIACRAWLER_PLATFORMS"
    )
    mediacrawler_timeout: float = Field(default=180.0, alias="MEDIACRAWLER_TIMEOUT")
    mediacrawler_save_path: str = Field(default="", alias="MEDIACRAWLER_SAVE_PATH")
    # Cookie 统一用同名前缀，platform_key 取 MediaCrawler 平台代码（xhs/dy/ks/bili/wb/tieba/zhihu）
    mediacrawler_cookies: str = Field(default="", alias="MEDIACRAWLER_COOKIES")

    # ---------- 小黑盒 ----------
    xiaoheihe_enabled: bool = Field(default=True, alias="XIAOHEIHE_ENABLED")
    xiaoheihe_mode: str = Field(default="browser", alias="XIAOHEIHE_MODE")
    xiaoheihe_cookie: str = Field(default="", alias="XIAOHEIHE_COOKIE")
    xiaoheihe_headless: bool = Field(default=True, alias="XIAOHEIHE_HEADLESS")
    xiaoheihe_timeout: float = Field(default=60.0, alias="XIAOHEIHE_TIMEOUT")
    xiaoheihe_user_data_dir: str = Field(
        default=str(BACKEND_DIR / ".cache" / "xiaoheihe-profile"),
        alias="XIAOHEIHE_USER_DATA_DIR",
    )

    # ---------- BOSS 直聘 ----------
    boss_enabled: bool = Field(default=True, alias="BOSS_ENABLED")
    boss_mode: str = Field(default="browser", alias="BOSS_MODE")
    boss_cookie: str = Field(default="", alias="BOSS_COOKIE")
    boss_city: str = Field(default="", alias="BOSS_CITY")
    boss_headless: bool = Field(default=True, alias="BOSS_HEADLESS")
    boss_timeout: float = Field(default=60.0, alias="BOSS_TIMEOUT")
    boss_user_data_dir: str = Field(
        default=str(BACKEND_DIR / ".cache" / "boss-profile"),
        alias="BOSS_USER_DATA_DIR",
    )

    @field_validator("max_concurrency", "max_results_per_source")
    @classmethod
    def _positive_int(cls, v: int) -> int:
        if v <= 0:
            raise ValueError("必须为正整数")
        return v

    # ---------- 派生属性 ----------
    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

    @property
    def mediacrawler_platform_list(self) -> list[str]:
        return [p.strip().lower() for p in self.mediacrawler_platforms.split(",") if p.strip()]

    def mediacrawler_cookie(self, platform: str) -> str:
        """读取指定平台的 Cookie。

        支持两种写法（后者优先）：
        - MEDIACRAWLER_COOKIES="xhs=<cookie>;wb=<cookie>"  （统一变量）
        - MEDIACRAWLER_COOKIE_XHS=<cookie>                 （独立变量，兼容旧配置）
        """
        key = (platform or "").strip().lower()
        if not key:
            return ""

        # 1) 独立变量（向后兼容）
        for name in (f"MEDIACRAWLER_COOKIE_{key}", f"MEDIACRAWLER_COOKIE_{key.upper()}"):
            value = _read_env_var(name)
            if value:
                return value

        # 2) 统一变量：以 ";" 分隔的 k=v 列表
        raw = _read_env_var("MEDIACRAWLER_COOKIES")
        if raw:
            for part in raw.split(";"):
                if "=" not in part:
                    continue
                k, _, v = part.partition("=")
                if k.strip().lower() == key and v.strip():
                    return v.strip()
        return ""

    @property
    def llm_ready(self) -> bool:
        return bool(self.deepseek_api_key)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
