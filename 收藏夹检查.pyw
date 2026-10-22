"""Edge 收藏夹链接可用性检查工具。

功能:
    - 自动定位 Edge 的 Bookmarks 文件（支持多个配置文件），也可手动选择
      Bookmarks 文件或浏览器导出的 HTML 收藏夹
    - 多线程并发检测每个收藏链接是否仍然可用，可切换「使用系统代理 / 直连」
    - 按 可用 / 可疑 / 失效 / 跳过 分类展示，可排序、双击打开、导出 CSV 报告

判定规则:
    - 失效：拿到 HTTP 响应且为 404 / 410，或重定向次数过多
    - 可疑：401/403/429、其它 4xx、5xx，以及所有「没拿到响应」的网络层失败
      （超时、DNS 失败、连接被拒、SSL 握手失败、内网不可达）
      这些往往是临时的（代理没开、网络抖动、对方限流），需人工确认
    - 可用：2xx
    - 跳过：chrome:// 等非 HTTP 协议、含 {{占位符}} 的链接

运行:
    python 收藏夹检查.pyw
"""

from __future__ import annotations

import bisect
import csv
import ipaddress
import json
import os
import queue
import socket
import threading
import time
import tkinter as tk
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional
from urllib.parse import urlparse

import requests
import urllib3
from requests.adapters import HTTPAdapter

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.0.0"
)

# 无法用 HTTP 请求验证的协议，直接跳过。
SKIP_SCHEMES = {
    "chrome",
    "chrome-extension",
    "edge",
    "edge-extension",
    "about",
    "javascript",
    "file",
    "data",
    "view-source",
    "devtools",
    "mailto",
    "tel",
}

LEVEL_LABELS = {"ok": "可用", "warn": "可疑", "bad": "失效", "skip": "跳过"}
LEVEL_RANK = {"bad": 0, "warn": 1, "skip": 2, "ok": 3}
LEVEL_TAGS = {"ok": "ok", "warn": "warn", "bad": "bad", "skip": "skip"}

ROOT_TITLES = {"bookmark_bar": "书签栏", "other": "其他收藏", "synced": "移动设备收藏"}

# 结果缓存：与脚本同目录，已加入 .gitignore
CACHE_FILE = Path(__file__).with_name("收藏夹检查_cache.json")
CACHE_VERSION = 1


# ---------------------------------------------------------------- 数据模型


@dataclass
class Bookmark:
    """一条收藏记录。"""

    name: str
    url: str
    folder: str = ""


@dataclass
class CheckResult:
    """一条检测结果。"""

    bookmark: Bookmark
    level: str  # ok / warn / bad / skip
    code: str
    elapsed: str
    note: str
    final_url: str = ""
    cached: bool = False  # 是否来自缓存（本次未重新请求）
    duplicate: int = 1  # 该 URL 在收藏夹中出现的次数（完全相同）
    near_duplicate: int = 1  # 归一化后相同的次数（含不同写法）

    @property
    def label(self) -> str:
        return LEVEL_LABELS[self.level]


# ---------------------------------------------------------------- 收藏夹解析


def find_bookmark_files() -> List[Path]:
    """定位本机所有 Edge 配置文件下的 Bookmarks 文件。"""
    bases: List[Path] = []
    local_appdata = os.environ.get("LOCALAPPDATA")
    if local_appdata:
        bases.append(Path(local_appdata) / "Microsoft" / "Edge" / "User Data")
    user_profile = os.environ.get("USERPROFILE")
    if user_profile:
        bases.append(
            Path(user_profile) / "AppData" / "Local" / "Microsoft" / "Edge" / "User Data"
        )

    found: List[Path] = []
    seen = set()
    for base in bases:
        if not base.is_dir():
            continue
        try:
            candidates = list(base.glob("*/Bookmarks"))
        except OSError:
            continue
        for candidate in candidates:
            key = str(candidate).casefold()
            if key in seen or not candidate.is_file():
                continue
            seen.add(key)
            found.append(candidate)

    # Default 配置排在前面。
    found.sort(key=lambda p: (p.parent.name.casefold() != "default", p.parent.name))
    return found


def parse_edge_bookmarks(path: Path) -> List[Bookmark]:
    """解析 Edge/Chrome 的 JSON 格式收藏夹文件。"""
    raw = path.read_text(encoding="utf-8-sig")
    data = json.loads(raw)
    bookmarks: List[Bookmark] = []

    def walk(node: dict, trail: List[str]) -> None:
        for child in node.get("children") or []:
            if not isinstance(child, dict):
                continue
            name = (child.get("name") or "").strip()
            node_type = child.get("type")
            if node_type == "url":
                url = (child.get("url") or "").strip()
                if url:
                    bookmarks.append(Bookmark(name or url, url, "/".join(trail)))
            elif node_type == "folder":
                walk(child, trail + [name or "未命名文件夹"])

    roots = data.get("roots") or {}
    for key, root in roots.items():
        if not isinstance(root, dict):
            continue
        title = ROOT_TITLES.get(key) or (root.get("name") or key)
        if root.get("type") == "url":
            url = (root.get("url") or "").strip()
            if url:
                bookmarks.append(Bookmark(root.get("name") or url, url, ""))
        else:
            walk(root, [title])
    return bookmarks


class _BookmarkHTMLParser(HTMLParser):
    """解析浏览器导出的 HTML 收藏夹，只保留链接与最近一级文件夹名。"""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.items: List[Bookmark] = []
        self._folder = ""
        self._buffer: List[str] = []
        self._in_h3 = False
        self._link: Optional[Dict[str, str]] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        if tag == "h3":
            self._in_h3 = True
            self._buffer = []
        elif tag == "a":
            self._link = {str(k).lower(): (v or "") for k, v in attrs}
            self._buffer = []

    def handle_data(self, data: str) -> None:
        if self._in_h3 or self._link is not None:
            self._buffer.append(data)

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag == "h3" and self._in_h3:
            self._folder = "".join(self._buffer).strip()
            self._in_h3 = False
            self._buffer = []
        elif tag == "a" and self._link is not None:
            href = (self._link.get("href") or "").strip()
            name = "".join(self._buffer).strip()
            if href:
                self.items.append(Bookmark(name or href, href, self._folder))
            self._link = None
            self._buffer = []


def load_bookmarks(path_text: str) -> List[Bookmark]:
    """根据扩展名判断格式并加载收藏夹。"""
    path = Path(path_text).expanduser()
    if not path.is_file():
        raise FileNotFoundError(f"找不到收藏夹文件：{path}")
    if path.suffix.lower() in {".html", ".htm"}:
        parser = _BookmarkHTMLParser()
        parser.feed(path.read_text(encoding="utf-8-sig", errors="replace"))
        return parser.items
    return parse_edge_bookmarks(path)


# ---------------------------------------------------------------- 结果缓存


def normalize_url(url: str) -> str:
    """归一化 URL 用于识别「近似重复」：忽略协议、www、末尾斜杠、锚点、大小写。"""
    try:
        parsed = urlparse(url.strip())
    except ValueError:
        return url.strip()
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path.rstrip("/")  # "/" 与 "" 视为相同
    query = f"?{parsed.query}" if parsed.query else ""
    # 忽略 http/https 差异：同一站点换协议通常仍是同一条收藏。
    return f"{host}{path}{query}"


def _cache_key(path_text: str, url: str) -> str:
    """缓存键：收藏夹文件 + URL。换配置或换文件时不会串味。"""
    return f"{Path(path_text).as_posix()}	{url}"


def load_cache() -> Dict[str, dict]:
    """读取缓存，文件不存在或损坏时返回空字典（不影响主流程）。"""
    try:
        raw = json.loads(CACHE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict) or raw.get("version") != CACHE_VERSION:
        return {}
    entries = raw.get("entries")
    return entries if isinstance(entries, dict) else {}


def save_cache(entries: Dict[str, dict]) -> None:
    """写缓存；失败时静默忽略（缓存不该影响正常使用）。"""
    payload = {
        "version": CACHE_VERSION,
        "saved_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "entries": entries,
    }
    try:
        CACHE_FILE.write_text(
            json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
    except OSError:
        pass


def _format_timestamp(seconds: float) -> str:
    return time.strftime("%Y-%m-%d %H:%M", time.localtime(seconds))


# ---------------------------------------------------------------- 链接检测

_thread_local = threading.local()


def _get_session() -> requests.Session:
    """每个工作线程复用一个 Session，避免重复握手。"""
    session = getattr(_thread_local, "session", None)
    if session is None:
        session = requests.Session()
        session.headers.update(
            {
                "User-Agent": USER_AGENT,
                "Accept": (
                    "text/html,application/xhtml+xml,application/xml;q=0.9,"
                    "image/avif,image/webp,*/*;q=0.8"
                ),
                "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            }
        )
        adapter = HTTPAdapter(pool_connections=4, pool_maxsize=8, max_retries=0)
        session.mount("http://", adapter)
        session.mount("https://", adapter)
        _thread_local.session = session
    return session


def _format_elapsed(seconds: float) -> str:
    if seconds < 1:
        return f"{seconds * 1000:.0f} ms"
    return f"{seconds:.1f} s"


def _same_host(a: str, b: str) -> bool:
    host_a = (urlparse(a).hostname or "").lower().removeprefix("www.")
    host_b = (urlparse(b).hostname or "").lower().removeprefix("www.")
    return host_a == host_b


def _classify_status(code: int) -> tuple[str, str]:
    """把 HTTP 状态码翻译成等级与说明。"""
    if 200 <= code < 300:
        return "ok", "正常"
    if code in (401, 407):
        return "warn", "需要登录认证"
    if code == 403:
        return "warn", "拒绝访问（可能触发反爬或需要登录）"
    if code == 429:
        return "warn", "请求过于频繁被限流"
    if code in (404, 410):
        return "bad", "页面不存在"
    if code == 451:
        return "warn", "因法律原因不可访问"
    if 400 <= code < 500:
        return "warn", "请求被拒绝"
    if code >= 500:
        return "warn", "服务器错误（可能临时故障）"
    return "warn", "未知状态"


def _describe_connection_error(exc: Exception) -> str:
    """把 ConnectionError 拆成更具体的说明（DNS / 拒绝 / 中断）。"""
    detail = str(exc).lower()
    if "getaddrinfo failed" in detail or "name or service not known" in detail:
        return "域名解析失败（域名可能已过期或 DNS 被污染）"
    if "name resolution" in detail or "nodename nor servname" in detail:
        return "域名解析失败（域名可能已过期或 DNS 被污染）"
    if "connection refused" in detail or "actively refused" in detail:
        return "连接被拒绝（服务未启动或端口已关闭）"
    if "reset by peer" in detail or "connection aborted" in detail:
        return "连接被对方重置（可能被拦截或服务异常）"
    if "no route to host" in detail or "network is unreachable" in detail:
        return "网络不可达（本机网络或路由异常）"
    if "tunnel connection failed" in detail:
        return "代理隧道建立失败（代理可能未运行）"
    return "无法连接（DNS 失败 / 连接被拒绝 / 网络不通）"


def _is_private_host(url: str) -> bool:
    """判断是否是局域网/本机地址。"""
    host = (urlparse(url).hostname or "").lower()
    if host in ("localhost",) or host.endswith(".local"):
        return True
    try:
        ip = ipaddress.ip_address(host)
    except ValueError:
        return False
    return ip.is_private or ip.is_loopback or ip.is_link_local


def system_proxy_map() -> Dict[str, str]:
    """读取系统代理（注册表/环境变量），返回 requests 可用的 proxies 字典。"""
    proxies: Dict[str, str] = {}
    try:
        raw = requests.utils.get_environ_proxies("https://example.com")
    except Exception:  # noqa: BLE001
        return proxies
    for scheme in ("http", "https"):
        value = raw.get(scheme)
        if value:
            proxies[scheme] = value
    return proxies


def describe_proxy(proxies: Dict[str, str]) -> str:
    if not proxies:
        return "直连"
    return proxies.get("https") or proxies.get("http") or "直连"


def probe_proxy(proxies: Dict[str, str], timeout: float = 4.0) -> tuple[bool, str]:
    """探测代理端口是否可连接，返回 (是否可用, 说明)。"""
    target = proxies.get("https") or proxies.get("http")
    if not target:
        return True, "直连"
    parsed = urlparse(target if "://" in target else f"http://{target}")
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        return True, f"无法解析代理地址 {target}"
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True, f"{host}:{port} 可用"
    except OSError as exc:
        return False, f"{host}:{port} 连接失败（{type(exc).__name__}）"


def check_url(
    url: str,
    timeout: float,
    retries: int,
    verify_ssl: bool,
    use_system_proxy: bool = True,
) -> tuple[str, str, str, str, str]:
    """检测单个 URL，返回 (等级, 状态码, 耗时, 备注, 最终地址)。"""
    parsed = urlparse(url)
    scheme = (parsed.scheme or "").lower()

    if "{{" in url and "}}" in url:
        return "skip", "-", "-", "链接含本地占位符，需在浏览器中还原", url
    if scheme in SKIP_SCHEMES:
        return "skip", "-", "-", f"{scheme} 协议无法用 HTTP 检测", url
    if scheme not in ("http", "https") or not parsed.netloc:
        return "skip", "-", "-", "不是有效的网页地址", url

    last_error = ""
    private_host = _is_private_host(url)
    proxies: Optional[Dict[str, str]] = None
    if not use_system_proxy:
        # 显式置空，覆盖 requests 从系统读取的代理。
        proxies = {"http": None, "https": None}
    attempts = max(0, retries) + 1
    for attempt in range(attempts):
        started = time.perf_counter()
        try:
            response = _get_session().get(
                url,
                timeout=(timeout, timeout),
                allow_redirects=True,
                stream=True,
                verify=verify_ssl,
                proxies=proxies,
            )
            elapsed = time.perf_counter() - started
            code = response.status_code
            final_url = response.url or url
            response.close()
        except requests.exceptions.SSLError as exc:
            # requests 会把部分握手失败也包装成 SSLError，只有证书校验失败才是证书问题。
            detail = str(exc).lower()
            if "certificate verify failed" in detail or "certificate_verify_failed" in detail:
                last_error = "SSL 证书无效（已开启证书校验）"
            else:
                last_error = "SSL 握手失败（域名失效或网络被拦截）"
        except requests.exceptions.Timeout:
            last_error = f"请求超时（{timeout:g} 秒）"
        except requests.exceptions.TooManyRedirects:
            last_error = "重定向次数过多"
        except requests.exceptions.ConnectionError as exc:
            last_error = _describe_connection_error(exc)
        except Exception as exc:  # noqa: BLE001 - 兜底，避免线程崩溃
            last_error = f"请求异常：{type(exc).__name__}"
        else:
            level, note = _classify_status(code)
            if code >= 500 and attempt < attempts - 1:
                time.sleep(0.5)
                continue
            if not _same_host(url, final_url):
                note = f"{note}；跳转到 {urlparse(final_url).hostname}"
            elif final_url != url:
                note = f"{note}；发生重定向"
            return level, str(code), _format_elapsed(elapsed), note, final_url

        if attempt < attempts - 1:
            time.sleep(0.5)

    # 没有拿到任何 HTTP 响应，说明是网络层问题（超时、连接被拒、DNS、SSL 握手）。
    # 这类失败常常是临时的：代理没开、网络抖动、对方限流、被墙。
    # 只有拿到 404/410 才算确定失效，因此这里统一降级为「可疑」，交给人工确认。
    if private_host:
        return "warn", "-", "-", f"内网地址不可达：{last_error}", url
    return "warn", "-", "-", f"网络层失败，需人工确认：{last_error}", url


# ---------------------------------------------------------------- 界面


class BookmarkCheckerApp:
    """主窗口。"""

    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.results: List[Optional[CheckResult]] = []
        self.order: List[int] = []  # 结果当前显示顺序（存书签下标）
        self.bookmarks: List[Bookmark] = []
        self.url_bookmark_index: Dict[str, List[int]] = {}
        self.url_dup_count: Dict[str, int] = {}
        self.url_near_count: Dict[str, int] = {}
        self.result_queue: "queue.Queue[tuple[str, tuple]]" = queue.Queue()
        self.stop_event = threading.Event()
        self.running = False
        self.total_tasks = 0
        self.finished_tasks = 0
        self.sort_key = ""
        self.sort_reverse = False
        self.cache_entries: Dict[str, dict] = {}
        self.cache_path_text = ""

        self.root.title("Edge 收藏夹链接检查")
        self.root.geometry("1180x720")
        self.root.minsize(900, 560)
        self._build_ui()
        self._auto_locate()
        self._refresh_proxy_info()
        self._refresh_cache_info()

    # ------------------------------------------------------------ 布局

    def _build_ui(self) -> None:
        style = ttk.Style()
        try:
            style.theme_use("vista")
        except tk.TclError:
            pass
        style.configure("Treeview", font=("Microsoft YaHei UI", 9), rowheight=24)
        style.configure("Treeview.Heading", font=("Microsoft YaHei UI", 9, "bold"))

        outer = ttk.Frame(self.root, padding=10)
        outer.pack(fill="both", expand=True)

        # 收藏夹文件
        file_row = ttk.Frame(outer)
        file_row.pack(fill="x")
        ttk.Label(file_row, text="收藏夹文件：").pack(side="left")
        self.path_var = tk.StringVar()
        self.path_combo = ttk.Combobox(file_row, textvariable=self.path_var, height=12)
        self.path_combo.pack(side="left", fill="x", expand=True, padx=(0, 6))
        ttk.Button(file_row, text="浏览…", width=8, command=self._browse).pack(side="left")
        ttk.Button(file_row, text="重新定位", width=9, command=self._auto_locate).pack(
            side="left", padx=(6, 0)
        )

        # 选项
        option_row = ttk.Frame(outer)
        option_row.pack(fill="x", pady=(8, 0))
        ttk.Label(option_row, text="超时(秒)").pack(side="left")
        self.timeout_var = tk.StringVar(value="10")
        ttk.Spinbox(
            option_row, from_=3, to=60, width=4, textvariable=self.timeout_var
        ).pack(side="left", padx=(2, 12))
        ttk.Label(option_row, text="并发数").pack(side="left")
        self.concurrency_var = tk.StringVar(value="8")
        ttk.Spinbox(
            option_row, from_=1, to=32, width=4, textvariable=self.concurrency_var
        ).pack(side="left", padx=(2, 12))
        ttk.Label(option_row, text="重试次数").pack(side="left")
        self.retries_var = tk.StringVar(value="1")
        ttk.Spinbox(
            option_row, from_=0, to=3, width=4, textvariable=self.retries_var
        ).pack(side="left", padx=(2, 12))
        self.verify_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            option_row, text="校验证书", variable=self.verify_var
        ).pack(side="left", padx=(0, 12))
        self.only_bad_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            option_row, text="只看失效/可疑", variable=self.only_bad_var,
            command=self._render_all,
        ).pack(side="left", padx=(0, 12))
        self.only_dup_var = tk.BooleanVar(value=False)
        ttk.Checkbutton(
            option_row, text="只看重复", variable=self.only_dup_var,
            command=self._render_all,
        ).pack(side="left")

        # 代理
        proxy_row = ttk.Frame(outer)
        proxy_row.pack(fill="x", pady=(6, 0))
        self.proxy_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            proxy_row,
            text="使用系统代理",
            variable=self.proxy_var,
            command=self._refresh_proxy_info,
        ).pack(side="left")
        self.proxy_info_var = tk.StringVar(value="")
        ttk.Label(proxy_row, textvariable=self.proxy_info_var).pack(
            side="left", padx=(8, 8)
        )
        ttk.Button(
            proxy_row, text="检测代理", width=9, command=self._probe_proxy_click
        ).pack(side="left")
        ttk.Separator(proxy_row, orient="vertical").pack(side="left", fill="y", padx=10)
        self.use_cache_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            proxy_row, text="复用缓存", variable=self.use_cache_var
        ).pack(side="left")
        self.cache_days_var = tk.StringVar(value="7")
        ttk.Spinbox(
            proxy_row, from_=1, to=365, width=4, textvariable=self.cache_days_var
        ).pack(side="left", padx=(2, 2))
        ttk.Label(proxy_row, text="天内").pack(side="left", padx=(0, 8))
        self.cache_info_var = tk.StringVar(value="")
        ttk.Label(proxy_row, textvariable=self.cache_info_var, foreground="#666").pack(
            side="left"
        )

        # 操作按钮
        action_row = ttk.Frame(outer)
        action_row.pack(fill="x", pady=8)
        self.start_button = ttk.Button(
            action_row, text="开始检查", width=12, command=self.start_check
        )
        self.start_button.pack(side="left")
        self.stop_button = ttk.Button(
            action_row, text="停止", width=8, command=self.stop_check, state="disabled"
        )
        self.stop_button.pack(side="left", padx=6)
        ttk.Button(
            action_row, text="导出 CSV", width=10, command=self.export_csv
        ).pack(side="left")
        ttk.Button(
            action_row, text="打开选中", width=10, command=self.open_selected
        ).pack(side="left")

        # 进度
        progress_row = ttk.Frame(outer)
        progress_row.pack(fill="x")
        self.progress = ttk.Progressbar(progress_row, mode="determinate")
        self.progress.pack(side="left", fill="x", expand=True)
        self.summary_var = tk.StringVar(value="就绪")
        ttk.Label(progress_row, textvariable=self.summary_var, width=42).pack(
            side="left", padx=(10, 0)
        )

        # 结果表
        table_frame = ttk.Frame(outer)
        table_frame.pack(fill="both", expand=True, pady=(8, 0))
        columns = ("status", "dup", "name", "url", "code", "elapsed", "note")
        headings = {
            "status": "状态",
            "dup": "重复",
            "name": "名称",
            "url": "链接",
            "code": "状态码",
            "elapsed": "耗时",
            "note": "备注",
        }
        widths = {
            "status": 60,
            "dup": 55,
            "name": 180,
            "url": 400,
            "code": 65,
            "elapsed": 75,
            "note": 280,
        }
        self.tree = ttk.Treeview(
            table_frame, columns=columns, show="headings", selectmode="extended"
        )
        for col in columns:
            self.tree.heading(
                col, text=headings[col], command=lambda c=col: self._sort_by(c)
            )
            self.tree.column(
                col, width=widths[col], anchor="w", stretch=col in ("url", "note")
            )
        y_scroll = ttk.Scrollbar(table_frame, orient="vertical", command=self.tree.yview)
        x_scroll = ttk.Scrollbar(
            table_frame, orient="horizontal", command=self.tree.xview
        )
        self.tree.configure(yscrollcommand=y_scroll.set, xscrollcommand=x_scroll.set)
        self.tree.grid(row=0, column=0, sticky="nsew")
        y_scroll.grid(row=0, column=1, sticky="ns")
        x_scroll.grid(row=1, column=0, sticky="ew")
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        self.tree.tag_configure("ok", foreground="#1b5e20")
        self.tree.tag_configure("warn", foreground="#e65100")
        self.tree.tag_configure("bad", foreground="#b71c1c")
        self.tree.tag_configure("skip", foreground="#757575")
        self.tree.bind("<Double-1>", lambda _event: self.open_selected())

    # ------------------------------------------------------------ 文件定位

    def _auto_locate(self) -> None:
        files = find_bookmark_files()
        values = [str(path) for path in files]
        self.path_combo["values"] = values
        if values:
            current = self.path_var.get()
            self.path_var.set(current if current in values else values[0])
            self.summary_var.set(f"已找到 {len(values)} 个收藏夹文件")
        else:
            self.summary_var.set("未自动找到 Edge 收藏夹，请手动选择")

    def _browse(self) -> None:
        path = filedialog.askopenfilename(
            title="选择收藏夹文件",
            filetypes=[
                ("收藏夹文件", "Bookmarks *.html *.htm"),
                ("所有文件", "*.*"),
            ],
        )
        if path:
            self.path_var.set(path)

    # ------------------------------------------------------------ 代理

    def _refresh_proxy_info(self) -> None:
        if not self.proxy_var.get():
            self.proxy_info_var.set("直连（忽略系统代理）")
            return
        proxies = system_proxy_map()
        if not proxies:
            self.proxy_info_var.set("系统未配置代理，将直连")
        else:
            self.proxy_info_var.set(f"当前代理：{describe_proxy(proxies)}")

    def _probe_proxy_click(self) -> None:
        if not self.proxy_var.get():
            messagebox.showinfo("代理状态", "当前为直连模式，未使用代理。")
            return
        proxies = system_proxy_map()
        if not proxies:
            messagebox.showinfo("代理状态", "系统未配置代理，检测将直连。")
            return
        ok, detail = probe_proxy(proxies)
        self.proxy_info_var.set(f"代理 {describe_proxy(proxies)}：{detail}")
        if ok:
            messagebox.showinfo("代理状态", f"代理可用：\n{detail}")
        else:
            messagebox.showwarning(
                "代理不可用",
                f"{detail}\n\n请先启动代理软件，否则大量链接会被误判为不可达。",
            )

    # ------------------------------------------------------------ 缓存

    def _refresh_cache_info(self) -> None:
        """显示缓存文件的存在情况与条目数。"""
        self.cache_entries = load_cache()
        if not self.cache_entries:
            self.cache_info_var.set("暂无缓存")
            return
        total = len(self.cache_entries)
        latest = 0.0
        for entry in self.cache_entries.values():
            latest = max(latest, float(entry.get("checked_at") or 0))
        stamp = _format_timestamp(latest) if latest else "未知时间"
        self.cache_info_var.set(f"缓存 {total} 条 · 最近 {stamp}")

    def _cache_ttl_seconds(self) -> float:
        try:
            days = float(self.cache_days_var.get())
        except ValueError:
            days = 7.0
        return max(1.0, days) * 86400

    def _cached_result(self, url: str, ttl: float) -> Optional[CheckResult]:
        """命中未过期缓存时返回结果，否则返回 None。"""
        entry = self.cache_entries.get(_cache_key(self.cache_path_text, url))
        if not isinstance(entry, dict):
            return None
        checked_at = float(entry.get("checked_at") or 0)
        if time.time() - checked_at > ttl:
            return None
        level = entry.get("level")
        if level not in LEVEL_LABELS:
            return None
        return CheckResult(
            Bookmark(entry.get("name") or url, url, entry.get("folder") or ""),
            level,
            str(entry.get("code") or "-"),
            str(entry.get("elapsed") or "-"),
            str(entry.get("note") or ""),
            str(entry.get("final_url") or url),
            cached=True,
        )

    def _store_cache_entry(self, result: CheckResult) -> None:
        key = _cache_key(self.cache_path_text, result.bookmark.url)
        self.cache_entries[key] = {
            "level": result.level,
            "code": result.code,
            "elapsed": result.elapsed,
            "note": result.note,
            "final_url": result.final_url,
            "name": result.bookmark.name,
            "folder": result.bookmark.folder,
            "checked_at": time.time(),
        }

    # ------------------------------------------------------------ 检查流程

    def start_check(self) -> None:
        if self.running:
            return
        path_text = self.path_var.get().strip()
        if not path_text:
            messagebox.showwarning("提示", "请先选择收藏夹文件")
            return

        try:
            bookmarks = load_bookmarks(path_text)
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("读取失败", f"无法解析收藏夹文件：\n{exc}")
            return

        if not bookmarks:
            messagebox.showinfo("提示", "这个文件里没有找到任何收藏链接")
            return

        self.bookmarks = bookmarks
        self.results = [None] * len(bookmarks)
        self.url_bookmark_index = {}
        for index, item in enumerate(bookmarks):
            self.url_bookmark_index.setdefault(item.url, []).append(index)
        # 同一 URL 出现多次即为重复，次数在生成结果时写入，供表格显示。
        self.url_dup_count = {
            url: len(indexes) for url, indexes in self.url_bookmark_index.items()
        }
        # 归一化后相同的（如 www / 末尾斜杠 / 锚点差异）算「近似重复」。
        self.url_near_count: Dict[str, int] = {}
        normalized_counter: Dict[str, int] = {}
        for url in self.url_bookmark_index:
            key = normalize_url(url)
            normalized_counter[key] = normalized_counter.get(key, 0) + 1
        for url in self.url_bookmark_index:
            self.url_near_count[url] = normalized_counter[normalize_url(url)]

        try:
            timeout = float(self.timeout_var.get())
            concurrency = max(1, int(self.concurrency_var.get()))
            retries = max(0, int(self.retries_var.get()))
        except ValueError:
            messagebox.showwarning("提示", "超时、并发、重试需要填写数字")
            return
        verify_ssl = bool(self.verify_var.get())
        use_system_proxy = bool(self.proxy_var.get())

        # 走代理时先确认代理端口活着，避免整批链接被误判。
        if use_system_proxy:
            proxies = system_proxy_map()
            if proxies:
                ok, detail = probe_proxy(proxies)
                self.proxy_info_var.set(f"代理 {describe_proxy(proxies)}：{detail}")
                if not ok and not messagebox.askyesno(
                    "代理不可用",
                    f"{detail}\n\n继续检查会把大量链接误判为不可达，"
                    "建议先启动代理软件。\n是否仍要继续？",
                ):
                    return

        self.tree.delete(*self.tree.get_children())
        self.order.clear()
        self.stop_event.clear()
        self.result_queue = queue.Queue()
        self.cache_path_text = path_text

        all_urls = list(self.url_bookmark_index.keys())
        pending_urls: List[str] = []
        reused = 0

        # 先填充未过期的缓存结果，剩下的才真正发请求。
        if self.use_cache_var.get():
            self._refresh_cache_info()
            ttl = self._cache_ttl_seconds()
            for url in all_urls:
                cached = self._cached_result(url, ttl)
                if cached is None:
                    pending_urls.append(url)
                else:
                    self._apply_cached(url, cached)
                    reused += 1
        else:
            pending_urls = all_urls

        self.total_tasks = len(all_urls)
        self.finished_tasks = reused
        self.running = True
        self.start_button.configure(state="disabled")
        self.stop_button.configure(state="normal")
        self.progress.configure(maximum=self.total_tasks, value=reused)

        if reused:
            self.summary_var.set(
                f"复用缓存 {reused} 条，待检测 {len(pending_urls)} 条…"
            )
        else:
            self.summary_var.set(
                f"开始检查 {len(bookmarks)} 条收藏（{len(pending_urls)} 个链接）…"
            )

        if not pending_urls:
            self._finish()
            return

        threading.Thread(
            target=self._worker,
            args=(
                pending_urls,
                timeout,
                concurrency,
                retries,
                verify_ssl,
                use_system_proxy,
            ),
            daemon=True,
        ).start()
        self.root.after(100, self._poll_queue)

    def _apply_cached(self, url: str, cached: CheckResult) -> None:
        """把缓存结果铺到所有引用该 URL 的书签上。"""
        for index in self.url_bookmark_index.get(url, []):
            bookmark = self.bookmarks[index]
            note = cached.note
            if note and not note.startswith("[缓存]"):
                note = f"[缓存] {note}"
            elif not note:
                note = "[缓存]"
            self.results[index] = CheckResult(
                bookmark,
                cached.level,
                cached.code,
                cached.elapsed,
                note,
                cached.final_url,
                cached=True,
                duplicate=self.url_dup_count.get(url, 1),
                near_duplicate=self.url_near_count.get(url, 1),
            )
            self._insert_row(index)

    def _worker(
        self,
        urls: List[str],
        timeout: float,
        concurrency: int,
        retries: int,
        verify_ssl: bool,
        use_system_proxy: bool,
    ) -> None:
        def task(url: str):
            if self.stop_event.is_set():
                return None
            return url, check_url(
                url, timeout, retries, verify_ssl, use_system_proxy
            )

        with ThreadPoolExecutor(max_workers=concurrency) as executor:
            for outcome in executor.map(task, urls):
                if outcome is not None:
                    self.result_queue.put(("done", outcome))
        self.result_queue.put(("finished", ()))

    def _poll_queue(self) -> None:
        drained = 0
        while drained < 60:
            try:
                kind, payload = self.result_queue.get_nowait()
            except queue.Empty:
                break
            drained += 1
            if kind == "done":
                url, data = payload
                self._apply_result(url, data)
            elif kind == "finished":
                self._finish()

        if self.running:
            self.root.after(100, self._poll_queue)

    def _apply_result(self, url: str, data: tuple) -> None:
        level, code, elapsed, note, final_url = data
        duplicate = self.url_dup_count.get(url, 1)
        for index in self.url_bookmark_index.get(url, []):
            self.results[index] = CheckResult(
                self.bookmarks[index],
                level,
                code,
                elapsed,
                note,
                final_url,
                duplicate=duplicate,
                near_duplicate=self.url_near_count.get(url, 1),
            )
            self._insert_row(index)
            self._store_cache_entry(self.results[index])
        self.finished_tasks += 1
        self.progress.configure(value=self.finished_tasks)
        self._update_summary()

    # 默认按“失效 → 可疑 → 跳过 → 可用”分组，组内按名称排序。
    def _order_key(self, index: int) -> tuple:
        result = self.results[index]
        return LEVEL_RANK.get(result.level, 9), result.bookmark.name.casefold()

    def _is_visible(self, index: int) -> bool:
        result = self.results[index]
        if result is None:
            return False
        if self.only_bad_var.get() and result.level == "ok":
            return False
        if self.only_dup_var.get() and max(result.duplicate, result.near_duplicate) <= 1:
            return False
        return True

    def _dup_text(self, result: CheckResult) -> str:
        if result.duplicate > 1:
            return f"×{result.duplicate}"
        if result.near_duplicate > 1:
            return f"≈{result.near_duplicate}"
        return ""

    def _row_values(self, result: CheckResult) -> tuple:
        return (
            result.label,
            self._dup_text(result),
            result.bookmark.name,
            result.bookmark.url,
            result.code,
            result.elapsed,
            result.note,
        )

    def _insert_row(self, index: int) -> None:
        """把新结果按当前排序插入列表（O(n) 定位，避免整表重绘）。"""
        position = bisect.bisect_right(
            [self._order_key(i) for i in self.order], self._order_key(index)
        )
        self.order.insert(position, index)
        if not self._is_visible(index):
            return
        result = self.results[index]
        tree_position = sum(1 for i in self.order[:position] if self._is_visible(i))
        self.tree.insert(
            "",
            tree_position,
            iid=str(index),
            values=self._row_values(result),
            tags=(LEVEL_TAGS[result.level],),
        )

    def _update_summary(self) -> None:
        counts = {"ok": 0, "warn": 0, "bad": 0, "skip": 0}
        cached_count = 0
        for result in self.results:
            if result is not None:
                counts[result.level] += 1
                if result.cached:
                    cached_count += 1
        text = (
            f"{self.finished_tasks}/{self.total_tasks} 个链接 · "
            f"可用 {counts['ok']} · 可疑 {counts['warn']} · "
            f"失效 {counts['bad']} · 跳过 {counts['skip']}"
        )
        if cached_count:
            text += f" · 其中缓存 {cached_count}"
        exact_groups = sum(1 for c in self.url_dup_count.values() if c > 1)
        near_groups = sum(1 for c in self.url_near_count.values() if c > 1)
        if exact_groups:
            dup_extra = sum(c - 1 for c in self.url_dup_count.values() if c > 1)
            text += f" · 重复 {exact_groups} 组(多 {dup_extra} 条)"
        if near_groups > exact_groups:
            text += f" · 近似重复 {near_groups - exact_groups} 组"
        self.summary_var.set(text)

    def _finish(self) -> None:
        self.running = False
        self.start_button.configure(state="normal")
        self.stop_button.configure(state="disabled")
        self.progress.configure(value=self.finished_tasks)
        self._update_summary()
        if self.stop_event.is_set():
            self.summary_var.set("已停止 · " + self.summary_var.get())
        self._sort_by("status", initial=True)
        if self.cache_entries:
            save_cache(self.cache_entries)
            self._refresh_cache_info()

    def stop_check(self) -> None:
        if not self.running:
            return
        self.stop_event.set()
        self.stop_button.configure(state="disabled")
        self.summary_var.set("正在停止…")

    # ------------------------------------------------------------ 结果操作

    def _sort_by(self, column: str, initial: bool = False) -> None:
        if not initial:
            if self.sort_key == column:
                self.sort_reverse = not self.sort_reverse
            else:
                self.sort_key, self.sort_reverse = column, False

        key_funcs = {
            "status": lambda r: (LEVEL_RANK.get(r.level, 9), r.bookmark.name.casefold()),
            "dup": lambda r: max(r.duplicate, r.near_duplicate),
            "name": lambda r: r.bookmark.name.casefold(),
            "url": lambda r: r.bookmark.url.casefold(),
            "code": lambda r: (r.code == "-", r.code),
            "elapsed": lambda r: r.elapsed,
            "note": lambda r: r.note,
        }
        key_func = key_funcs.get(column)
        if key_func is None or not self.order:
            return
        if initial:
            self.sort_key, self.sort_reverse = column, False
        self.order.sort(
            key=lambda i: key_func(self.results[i]), reverse=self.sort_reverse
        )
        self._render_all()

    def _render_all(self) -> None:
        self.tree.delete(*self.tree.get_children())
        for index in self.order:
            if not self._is_visible(index):
                continue
            result = self.results[index]
            self.tree.insert(
                "",
                "end",
                iid=str(index),
                values=self._row_values(result),
                tags=(LEVEL_TAGS[result.level],),
            )

    def _selected_results(self) -> List[CheckResult]:
        selected: List[CheckResult] = []
        for iid in self.tree.selection():
            try:
                result = self.results[int(iid)]
            except (ValueError, IndexError):
                continue
            if result is not None:
                selected.append(result)
        return selected

    def open_selected(self) -> None:
        selected = self._selected_results()
        if not selected:
            messagebox.showinfo("提示", "请先在列表中选择一条收藏")
            return
        for result in selected:
            webbrowser.open(result.bookmark.url)

    def export_csv(self) -> None:
        rows = [r for r in self.results if r is not None]
        if not rows:
            messagebox.showinfo("提示", "还没有检测结果可以导出")
            return
        default_name = Path(self.path_var.get()).stem or "bookmarks"
        path = filedialog.asksaveasfilename(
            title="保存检查报告",
            defaultextension=".csv",
            initialfile=f"{default_name}_检查报告.csv",
            filetypes=[("CSV 文件", "*.csv")],
        )
        if not path:
            return
        with open(path, "w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle)
            writer.writerow(
                [
                    "状态", "名称", "所在文件夹", "链接",
                    "状态码", "耗时", "备注", "最终地址", "数据来源",
                    "重复次数", "近似重复次数", "归一化地址",
                ]
            )
            for result in rows:
                writer.writerow(
                    [
                        result.label,
                        result.bookmark.name,
                        result.bookmark.folder,
                        result.bookmark.url,
                        result.code,
                        result.elapsed,
                        result.note,
                        result.final_url,
                        "缓存" if result.cached else "本次实测",
                        result.duplicate,
                        result.near_duplicate,
                        normalize_url(result.bookmark.url),
                    ]
                )
        messagebox.showinfo("导出成功", f"报告已保存到：\n{path}")


def main() -> None:
    root = tk.Tk()
    BookmarkCheckerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
