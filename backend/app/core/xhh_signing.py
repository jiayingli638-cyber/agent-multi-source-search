"""小黑盒（xiaoheihe.cn）网页接口签名算法。

小黑盒接口要求 `hkey` / `_time` / `nonce` 三个签名参数，算法为自定义混淆的
MD5 + 有限域列混合（GF(2^8)）+ 自定义字符表映射。本模块为等价实现。

算法来源：公开的网页端行为分析（better-XiaoHeiHe 等开源项目对
`api.xiaoheihe.cn` 接口的说明），仅用于个人学习研究用途的内容聚合。
"""
from __future__ import annotations

import hashlib
import random
import time

# 自定义字符表（24 个字符）
ALPHABET = "AB45STUVWZEFGJ6CH01D237IXYPQRKLMN89"


def md5(text: str) -> str:
    """标准 MD5，小写十六进制。"""
    return hashlib.md5(text.encode("utf-8")).hexdigest()


# ---------------- GF(2^8) 有限域运算 ----------------
def _xtime(value: int) -> int:
    """乘 2（模 x^8+x^4+x^3+x+1）。"""
    if value & 0x80:
        return ((value << 1) ^ 0x1B) & 0xFF
    return (value << 1) & 0xFF


def _q(v: int) -> int:
    return _xtime(v) ^ v


def _r(v: int) -> int:
    return _q(_xtime(v))


def _y(v: int) -> int:
    return _r(_q(_xtime(v)))


def _g(v: int) -> int:
    return _y(v) ^ _r(v) ^ _q(v)


def mix_columns(values: list[int]) -> list[int]:
    """等价 JS 的 mixColumns：4 个字节一组做列混合。"""
    a, b, c, d = values[0], values[1], values[2], values[3]
    return [
        (_g(a) ^ _y(b) ^ _r(c) ^ _q(d)) & 0xFF,
        (_q(a) ^ _g(b) ^ _y(c) ^ _r(d)) & 0xFF,
        (_r(a) ^ _q(b) ^ _g(c) ^ _y(d)) & 0xFF,
        (_y(a) ^ _r(b) ^ _q(c) ^ _g(d)) & 0xFF,
    ]


# ---------------- 字符表映射 ----------------
def _map_by_alphabet(value: str, end: int | None = None) -> str:
    """把每个字符按 code % len(source) 映射到字符表。

    end 为负数时等价 JS 的 `alphabet.slice(0, end)`（去掉末尾 |end| 个字符）。
    """
    if end is None:
        source = ALPHABET
    elif end < 0:
        source = ALPHABET[:end]
    else:
        source = ALPHABET[:end]
    return "".join(source[ord(ch) % len(source)] for ch in value)


def _path_to_alphabet(value: str) -> str:
    return "".join(ALPHABET[ord(ch) % len(ALPHABET)] for ch in value)


def _interleave(values: list[str]) -> str:
    """按列交错拼接多个字符串（等价 JS interleave）。"""
    if not values:
        return ""
    out: list[str] = []
    longest = max(len(v) for v in values)
    for i in range(longest):
        for v in values:
            if i < len(v):
                out.append(v[i])
    return "".join(out)


# ---------------- 主入口 ----------------
def create_signed_params(path: str) -> dict[str, object]:
    """为指定接口路径生成 hkey / _time / nonce。"""
    ts = int(time.time())
    nonce = md5(f"{ts}{random.random()}").upper()

    # 路径归一化：/a/b/c -> /a/b/c/
    normalized = "/" + "/".join(seg for seg in path.split("/") if seg) + "/"

    seed = _interleave([
        _map_by_alphabet(str(ts + 1), -2),
        _path_to_alphabet(normalized),
        _path_to_alphabet(nonce),
    ])[:20]

    digest = md5(seed)
    checksum = str(sum(mix_columns([ord(c) for c in digest[-6:]])) % 100).zfill(2)

    return {
        "hkey": _map_by_alphabet(digest[:5], -4) + checksum,
        "_time": ts,
        "nonce": nonce,
    }


def base_api_params() -> dict[str, str]:
    """网页端基础环境参数。"""
    return {
        "os_type": "web",
        "app": "heybox",
        "client_type": "web",
        "version": "999.0.4",
        "web_version": "2.5",
        "x_client_type": "web",
        "x_app": "heybox_website",
        "x_os_type": "Windows",
        "device_info": "Chrome",
    }
