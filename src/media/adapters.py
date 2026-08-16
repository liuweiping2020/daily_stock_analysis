# -*- coding: utf-8 -*-
"""多平台适配器：微信公众号、知乎、通用剪贴板导出、雪球、微博、头条等。

设计原则：
- 平台适配器以统一 ``publish(title, markdown, html, **kwargs)`` 作为主入口。
- 外部 API 不可达或凭据缺失时，抛出 ``MediaAdapterError``，由服务层统一
  写入 task.error_code/error_message 并决定是否重试。
- 所有适配器的返回统一为 dict：
  ``{ "ok": bool, "article_id": str|None, "url": str|None, "extra": dict }``
- 对依赖外部第三方 HTTP 库（wechatpy、zhihu-oauth 等）采用可选导入：
  未安装时返回 ``ok=False`` + 明确提示安装命令，不拖垮整个应用。
"""

from __future__ import annotations

import base64
import json
import logging
import re
from dataclasses import dataclass, field, asdict
from datetime import datetime
from typing import Any, Dict, List, Optional


logger = logging.getLogger(__name__)


# --------------------------------------------------------------------------- #
# Exceptions
# --------------------------------------------------------------------------- #
class MediaAdapterError(Exception):
    """平台适配器业务错误。"""

    def __init__(self, code: str, message: str, raw: Any = None):
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message
        self.raw = raw


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #
@dataclass
class PublishPayload:
    """统一发布载荷，服务层把分析结果预处理后传给适配器。"""

    title: str
    markdown: str = ""
    html: str = ""
    summary: Optional[str] = None
    tags: List[str] = field(default_factory=list)
    cover_url: Optional[str] = None
    original_author: Optional[str] = None
    # 可选：分析/复盘日期，用于公众号封面标题里展示时间
    reference_date: Optional[str] = None
    # 平台特定扩展参数
    platform_options: Dict[str, Any] = field(default_factory=dict)


@dataclass
class PublishResult:
    ok: bool
    article_id: Optional[str] = None
    url: Optional[str] = None
    extra: Dict[str, Any] = field(default_factory=dict)
    error_code: Optional[str] = None
    error_message: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------- #
# Base adapter
# --------------------------------------------------------------------------- #
class BaseMediaAdapter:
    """所有平台适配器的基类。"""

    # 平台唯一编码，对应 MediaPlatform.platform_code
    PLATFORM_CODE: str = "base"
    # 展示名
    PLATFORM_NAME: str = "Base"
    # 需要的凭据字段名列表（用于 Web 端提示）
    REQUIRED_CREDENTIAL_KEYS: List[str] = []

    def __init__(self, credentials: Optional[Dict[str, Any]] = None,
                 extra: Optional[Dict[str, Any]] = None) -> None:
        self.credentials = credentials or {}
        self.extra = extra or {}

    # ------------------------- 公共工具方法 ------------------------- #

    @staticmethod
    def _strip_html(html: str) -> str:
        """简单去 HTML，用于生成纯文本摘要或某些平台纯文本兜底。"""
        if not html:
            return ""
        text = re.sub(r"<br\s*/?>", "\n", html, flags=re.I)
        text = re.sub(r"</p>\s*<p[^>]*>", "\n\n", text, flags=re.I)
        text = re.sub(r"<[^>]+>", "", text)
        return text.strip()

    @staticmethod
    def _ensure_html(markdown: str, html: str) -> str:
        """优先返回 html，若缺失则用 markdown 做最小幅度转义（不依赖第三方库）。"""
        if html:
            return html
        if not markdown:
            return ""
        # 最小实现：段落转换 + 加粗/标题
        out: List[str] = []
        for block in re.split(r"\n{2,}", markdown):
            block = block.strip()
            if not block:
                continue
            if block.startswith("###### "):
                out.append(f"<h6>{block[7:]}</h6>")
            elif block.startswith("##### "):
                out.append(f"<h5>{block[6:]}</h5>")
            elif block.startswith("#### "):
                out.append(f"<h4>{block[5:]}</h4>")
            elif block.startswith("### "):
                out.append(f"<h3>{block[4:]}</h3>")
            elif block.startswith("## "):
                out.append(f"<h2>{block[3:]}</h2>")
            elif block.startswith("# "):
                out.append(f"<h1>{block[2:]}</h1>")
            elif block.startswith(("- ", "* ")):
                items = []
                for line in block.splitlines():
                    m = re.match(r"[-*]\s+(.*)", line)
                    if m:
                        items.append(f"<li>{m.group(1)}</li>")
                if items:
                    out.append("<ul>" + "".join(items) + "</ul>")
            else:
                # inline **bold** and `code`
                b = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", block)
                b = re.sub(r"`([^`]+)`", r"<code>\1</code>", b)
                b = b.replace("\n", "<br/>")
                out.append(f"<p>{b}</p>")
        return "\n".join(out)

    # ------------------------- 主入口 ------------------------- #

    def publish(self, payload: PublishPayload) -> PublishResult:
        """子类重写。"""
        raise NotImplementedError


# --------------------------------------------------------------------------- #
# 1. 微信公众号草稿箱（WeChat Official Account, MP）
# --------------------------------------------------------------------------- #
class WechatMPAdapter(BaseMediaAdapter):
    """微信公众号图文草稿箱 + 可选群发。

    凭据字段（credentials_json）：
    - app_id           : 公众号 AppID
    - app_secret       : 公众号 AppSecret
    - to_user_open_ids : 可选，群发 open_id 列表（若需要 publish 而非仅草稿）
    （优先使用 access_token 缓存，凭据接口调用方无需显式存储 token）

    说明：使用公众号官方 /cgi-bin/material/add_draft 写入草稿箱，
    正式发布建议仍在公众号后台人工确认；如需自动发布，可再调
    /cgi-bin/freepublish/submit。这里默认仅写入草稿箱，更安全。
    """

    PLATFORM_CODE = "wechat_mp"
    PLATFORM_NAME = "微信公众号"
    REQUIRED_CREDENTIAL_KEYS = ["app_id", "app_secret"]

    _ACCESS_TOKEN_CACHE: Dict[str, Dict[str, Any]] = {}  # (app_id) -> {token, expire_ts}

    # 纯 Python 的最小网络请求封装，避免引入强依赖
    @staticmethod
    def _http_get_json(url: str, timeout: float = 10.0) -> Dict[str, Any]:
        import urllib.request
        import urllib.error
        try:
            with urllib.request.urlopen(url, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", errors="replace")
            try:
                return json.loads(b)
            except Exception:
                return {"errcode": e.code, "errmsg": b}
        except Exception as e:
            return {"errcode": "NET_ERROR", "errmsg": str(e)}

    @staticmethod
    def _http_post_json(url: str, data: Dict[str, Any], timeout: float = 30.0) -> Dict[str, Any]:
        import urllib.request
        import urllib.error
        try:
            raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            req = urllib.request.Request(
                url, data=raw,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", errors="replace")
            try:
                return json.loads(b)
            except Exception:
                return {"errcode": e.code, "errmsg": b}
        except Exception as e:
            return {"errcode": "NET_ERROR", "errmsg": str(e)}

    def _get_access_token(self, app_id: str, app_secret: str) -> str:
        cache_key = app_id
        now_ts = int(datetime.now().timestamp())
        cached = self._ACCESS_TOKEN_CACHE.get(cache_key)
        if cached and cached["expire_ts"] - now_ts > 60:
            return cached["token"]
        url = (
            "https://api.weixin.qq.com/cgi-bin/token"
            f"?grant_type=client_credential&appid={app_id}&secret={app_secret}"
        )
        data = self._http_get_json(url)
        token = data.get("access_token")
        expires_in = int(data.get("expires_in", 7200))
        errcode = data.get("errcode")
        if not token or errcode:
            raise MediaAdapterError(
                code=f"WECHAT_TOKEN_{errcode or 'EMPTY'}",
                message=data.get("errmsg", "获取 access_token 失败"),
                raw=data,
            )
        self._ACCESS_TOKEN_CACHE[cache_key] = {
            "token": token,
            "expire_ts": now_ts + expires_in,
        }
        return token

    def publish(self, payload: PublishPayload) -> PublishResult:
        app_id = (self.credentials or {}).get("app_id")
        app_secret = (self.credentials or {}).get("app_secret")
        if not app_id or not app_secret:
            return PublishResult(
                ok=False,
                error_code="CREDENTIAL_MISSING",
                error_message=f"{self.PLATFORM_NAME} 需要配置 app_id / app_secret",
            )
        try:
            token = self._get_access_token(app_id, app_secret)
        except MediaAdapterError as e:
            return PublishResult(ok=False, error_code=e.code, error_message=e.message, extra={"raw": e.raw})

        html = self._ensure_html(payload.markdown, payload.html)
        # 微信公众号图文支持较完整 HTML，但需注意外链图片需走素材上传；这里
        # 仅作 HTML 写入，如遇图片被吞，后续可再补素材上传流程。
        thumb = payload.cover_url or self.extra.get("thumb_media_id")
        article_item: Dict[str, Any] = {
            "title": payload.title,
            "content": html,
            "digest": payload.summary or self._strip_html(html)[:120],
            "content_source_url": "",
            "thumb_media_id": thumb if thumb and not str(thumb).startswith("http") else "",
            "show_cover_pic": 1,
            "need_open_comment": self.extra.get("need_open_comment", 0),
            "only_fans_can_comment": self.extra.get("only_fans_can_comment", 0),
            "author": payload.original_author or self.extra.get("author", ""),
        }
        add_url = (
            "https://api.weixin.qq.com/cgi-bin/draft/add"
            f"?access_token={token}"
        )
        data = self._http_post_json(add_url, {"articles": [article_item]})
        errcode = data.get("errcode")
        if errcode and int(errcode) != 0:
            return PublishResult(
                ok=False,
                error_code=f"WECHAT_DRAFT_{errcode}",
                error_message=data.get("errmsg", "写入草稿箱失败"),
                extra=data,
            )
        media_id = data.get("media_id")
        # 微信草稿箱 URL 无法直接预览到用户，后台可见
        return PublishResult(
            ok=True,
            article_id=media_id,
            url=None,
            extra={"note": "已写入公众号草稿箱，请登录公众平台确认后发布"},
        )


# --------------------------------------------------------------------------- #
# 2. 知乎（Zhihu）文章 / 想法
# --------------------------------------------------------------------------- #
class ZhihuAdapter(BaseMediaAdapter):
    """知乎文章或想法发布。

    凭据字段（credentials_json）：
    - cookies        : 登录后复制的 Cookie 字符串（完整 Cookie header）
    - z_c0           : 可单独填入 z_c0 token（知乎主登录态）
    - column_id      : 可选，专栏 ID；未填则发布为非专栏文章
    说明：知乎官方开放平台目前对一般开发者不直接开放写文章 API，
    因此采用 HTTP 模拟草稿提交方式；若凭据失效，接口会返回 401/403，
    服务层会记录 error_message 并提示用户更新 Cookie。
    """

    PLATFORM_CODE = "zhihu"
    PLATFORM_NAME = "知乎"
    REQUIRED_CREDENTIAL_KEYS = ["z_c0"]

    @staticmethod
    def _req(method: str, url: str, *, headers: Dict[str, str],
             data: Optional[Dict[str, Any]] = None, timeout: float = 20.0) -> Dict[str, Any]:
        import urllib.request
        import urllib.error
        try:
            if data is not None:
                raw = json.dumps(data, ensure_ascii=False).encode("utf-8")
            else:
                raw = None
            req = urllib.request.Request(url, data=raw, headers=headers, method=method)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                try:
                    return json.loads(body)
                except Exception:
                    return {"status": resp.status, "raw": body}
        except urllib.error.HTTPError as e:
            b = e.read().decode("utf-8", errors="replace")
            try:
                j = json.loads(b)
                j.setdefault("_status", e.code)
                return j
            except Exception:
                return {"_status": e.code, "raw": b}
        except Exception as e:
            return {"_status": "NET_ERROR", "raw": str(e)}

    def publish(self, payload: PublishPayload) -> PublishResult:
        creds = self.credentials or {}
        z_c0 = creds.get("z_c0")
        cookies_full = creds.get("cookies")
        if not z_c0 and not cookies_full:
            return PublishResult(
                ok=False,
                error_code="CREDENTIAL_MISSING",
                error_message="知乎需要 z_c0 或完整 Cookie",
            )
        cookie_header = (
            cookies_full if cookies_full else f"z_c0={z_c0}"
        )
        headers = {
            "Content-Type": "application/json",
            "Cookie": cookie_header,
            "User-Agent": (
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/122.0 Safari/537.36"
            ),
            "Referer": "https://zhuanlan.zhihu.com/",
            "x-requested-with": "fetch",
        }
        column_id = payload.platform_options.get("column_id") or self.extra.get("column_id")
        html = self._ensure_html(payload.markdown, payload.html)
        # 知乎专栏文章草稿 API（此接口会因知乎版本变化而变化，失败时给出明确提示）
        if column_id:
            draft_url = f"https://zhuanlan.zhihu.com/api/columns/{column_id}/drafts"
        else:
            draft_url = "https://zhuanlan.zhihu.com/api/articles/drafts"
        body = {
            "title": payload.title,
            "content": html,
            "delta_time": 0,
        }
        resp = self._req("POST", draft_url, headers=headers, data=body)
        status = resp.get("_status") or resp.get("status")
        article_id = resp.get("id") or resp.get("draft_id")
        if status and str(status) not in ("200", "0"):
            return PublishResult(
                ok=False,
                error_code=f"ZHIHU_{status or 'UNKNOWN'}",
                error_message=resp.get("message") or resp.get("raw") or "知乎草稿提交失败",
                extra=resp,
            )
        # 知乎草稿默认不自动发布；这里返回草稿链接，用户在专栏后台确认即可
        url = None
        if article_id:
            url = f"https://zhuanlan.zhihu.com/p/{article_id}" if str(article_id).isdigit() else None
        return PublishResult(
            ok=True,
            article_id=str(article_id) if article_id else None,
            url=url,
            extra={"note": "已写入知乎草稿/文章，请在专栏后台确认后发布", "raw": resp},
        )


# --------------------------------------------------------------------------- #
# 3. 通用导出（Clipboard Export）— 不依赖外部，始终可用
# --------------------------------------------------------------------------- #
class ClipboardExportAdapter(BaseMediaAdapter):
    """把内容打包成结构化 JSON/Markdown/HTML 输出，供前端复制到剪贴板。

    该适配器不访问外部网络，不进行真实发布，只返回 payload。
    作为「未配置任何平台凭据」时的保底方案，也是调试最常用的出口。
    """

    PLATFORM_CODE = "clipboard_export"
    PLATFORM_NAME = "通用导出（剪贴板）"
    REQUIRED_CREDENTIAL_KEYS: List[str] = []

    def publish(self, payload: PublishPayload) -> PublishResult:
        html = self._ensure_html(payload.markdown, payload.html)
        plain = self._strip_html(html)
        export = {
            "title": payload.title,
            "summary": payload.summary or plain[:240],
            "tags": payload.tags,
            "cover_url": payload.cover_url,
            "markdown": payload.markdown,
            "html": html,
            "plain_text": plain,
            "author": payload.original_author,
            "reference_date": payload.reference_date,
            "generated_at": datetime.now().isoformat(timespec="seconds"),
            # 为适配 doocs/cose 类浏览器扩展发布的需求，提供兼容字段
            "cose_compatible": {
                "title": payload.title,
                "content": payload.markdown,
                "tags": payload.tags,
                "description": payload.summary or plain[:240],
                "cover": payload.cover_url,
            },
        }
        # 生成一段 compact JSON + base64，方便前端一键复制/重放
        compact_json = json.dumps(export, ensure_ascii=False, separators=(",", ":"))
        b64 = base64.b64encode(compact_json.encode("utf-8")).decode("ascii")
        return PublishResult(
            ok=True,
            article_id=f"export-{abs(hash(compact_json)) % (10**10)}",
            url=None,
            extra={
                "export": export,
                "compact_json": compact_json,
                "base64_json": b64,
                "frontends": {
                    "copy_markdown": payload.markdown,
                    "copy_html": html,
                    "copy_cose_json": json.dumps(
                        export["cose_compatible"], ensure_ascii=False
                    ),
                },
            },
        )


# --------------------------------------------------------------------------- #
# 4. 雪球 (Xueqiu) — 占位 + HTTP 模拟
# --------------------------------------------------------------------------- #
class XueqiuAdapter(BaseMediaAdapter):
    """雪球长文发布（基于 Cookie 会话）。

    凭据字段：cookies（雪球登录后的 Cookie 头）。
    若未装依赖或 Cookie 失效，错误信息会清晰提示，不会静默失败。
    """

    PLATFORM_CODE = "xueqiu"
    PLATFORM_NAME = "雪球"
    REQUIRED_CREDENTIAL_KEYS = ["cookies"]

    def publish(self, payload: PublishPayload) -> PublishResult:
        cookies = (self.credentials or {}).get("cookies")
        if not cookies:
            return PublishResult(ok=False, error_code="CREDENTIAL_MISSING",
                                 error_message="雪球需要登录后 cookies")
        markdown = payload.markdown
        if not markdown:
            markdown = self._strip_html(self._ensure_html(payload.markdown, payload.html))
        # 雪球长文接口会变化，这里作为占位实现 + 清晰提示
        return PublishResult(
            ok=False,
            error_code="XUEQIU_NOT_IMPLEMENTED",
            error_message=(
                "雪球自动发布暂未内置。可使用「通用导出」拿到 Markdown，"
                "粘贴到 https://xueqiu.com/write 发布。"
            ),
            extra={"fallback_markdown": markdown},
        )


# --------------------------------------------------------------------------- #
# 5. 微博 (Weibo) 占位适配器
# --------------------------------------------------------------------------- #
class WeiboAdapter(BaseMediaAdapter):
    PLATFORM_CODE = "weibo"
    PLATFORM_NAME = "微博"
    REQUIRED_CREDENTIAL_KEYS = ["cookies"]

    def publish(self, payload: PublishPayload) -> PublishResult:
        if not (self.credentials or {}).get("cookies"):
            return PublishResult(ok=False, error_code="CREDENTIAL_MISSING",
                                 error_message="微博需要登录后 cookies")
        text = (payload.summary or "") + "\n\n" + (payload.markdown or "")
        text = text.strip() or self._strip_html(
            self._ensure_html(payload.markdown, payload.html)
        )
        return PublishResult(
            ok=False,
            error_code="WEIBO_NOT_IMPLEMENTED",
            error_message=(
                "微博自动发布暂未内置。可使用「通用导出」拿到摘要+Markdown，"
                "粘贴到 https://weibo.com/new 发布。"
            ),
            extra={"fallback_text": text[:500]},
        )


# --------------------------------------------------------------------------- #
# 6. 今日头条 (Toutiao) 占位适配器
# --------------------------------------------------------------------------- #
class ToutiaoAdapter(BaseMediaAdapter):
    PLATFORM_CODE = "toutiao"
    PLATFORM_NAME = "今日头条"
    REQUIRED_CREDENTIAL_KEYS = ["cookies"]

    def publish(self, payload: PublishPayload) -> PublishResult:
        if not (self.credentials or {}).get("cookies"):
            return PublishResult(ok=False, error_code="CREDENTIAL_MISSING",
                                 error_message="头条需要登录后 cookies")
        return PublishResult(
            ok=False,
            error_code="TOUTIAO_NOT_IMPLEMENTED",
            error_message=(
                "今日头条自动发布暂未内置。可使用「通用导出」拿到 Markdown/HTML，"
                "粘贴到 https://mp.toutiao.com/profile_v4/graphic/publish 发布。"
            ),
            extra={"fallback_title": payload.title},
        )


# --------------------------------------------------------------------------- #
# Registry
# --------------------------------------------------------------------------- #
_ADAPTER_REGISTRY: Dict[str, type] = {
    cls.PLATFORM_CODE: cls  # type: ignore[assignment]
    for cls in [
        WechatMPAdapter,
        ZhihuAdapter,
        ClipboardExportAdapter,
        XueqiuAdapter,
        WeiboAdapter,
        ToutiaoAdapter,
    ]
}


def list_supported_platforms() -> List[Dict[str, Any]]:
    """列出所有支持的平台元信息（前端展示用）。"""
    return [
        {
            "platform_code": cls.PLATFORM_CODE,
            "platform_name": cls.PLATFORM_NAME,
            "required_credential_keys": list(cls.REQUIRED_CREDENTIAL_KEYS),
        }
        for cls in _ADAPTER_REGISTRY.values()
    ]


def get_adapter_class(platform_code: str) -> Optional[type]:
    return _ADAPTER_REGISTRY.get(platform_code)


def build_adapter(*, platform_code: str,
                  credentials: Optional[Dict[str, Any]] = None,
                  extra: Optional[Dict[str, Any]] = None) -> BaseMediaAdapter:
    cls = get_adapter_class(platform_code)
    if cls is None:
        raise MediaAdapterError(
            code="PLATFORM_NOT_SUPPORTED",
            message=f"未支持的平台编码: {platform_code}",
        )
    return cls(credentials=credentials, extra=extra)
