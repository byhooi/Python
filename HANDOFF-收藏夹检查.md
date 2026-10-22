# Handoff — Edge 收藏夹链接检查工具

> 会话交接文档。记录已完成的工作、关键决策、验证结论与未完成事项。
> 最后更新：本次会话结束

---

## 1. 交付物

| 文件 | 状态 | 说明 |
|---|---|---|
| `收藏夹检查.pyw` | ✅ 完成，已实测 | 新增文件，未提交 git |
| `收藏夹检查_cache.json` | 运行时生成 | 结果缓存，**已加入 .gitignore** |
| `__pycache__/` | ⚠️ 测试残留 | 可删除，建议加进 `.gitignore` |
| Edge `Bookmarks` | ✅ 未改动 | 全程只读，大小 148779 字节未变 |

**未改动任何既有文件。** 依赖仅 `requests`（`requirements.txt` 已包含）。

运行方式：双击，或 `python 收藏夹检查.pyw`

---

## 2. 需求演进（按时间顺序）

1. **初始需求**：写一个 pyw，检查 Edge 收藏夹里的 URL 是否还有效
2. **追加需求 1**：确认走直连还是系统代理 → 发现是走系统代理，遂加「是否使用系统代理」开关
3. **追加需求 2**：修复分类 bug —— 网络层错误被误判为「失效」
4. **追加需求 3**：加删除功能（跳过，见 §6）
5. **本次**：写 handoff

---

## 3. 功能清单

### 3.1 收藏夹来源
- 自动扫描 Edge 全部配置文件的 `Bookmarks`（本机实测发现 4 个：`Default`、`Profile 5`、`Profile 8`、`Profile 9`）
- 下拉框切换，`Default` 排最前
- 也支持手动选择浏览器导出的 HTML 收藏夹（自动按扩展名 `.html/.htm` 识别）
- 支持拖入任意路径，也支持 `文件 → 浏览…`

### 3.2 检测逻辑（`check_url`，第 351 行）
- 多线程并发（`ThreadPoolExecutor`，默认 8），线程内复用 `requests.Session`（`_get_session` + `threading.local`）
- `stream=True` 只取响应头，不下载正文
- 同一 URL 出现多次只请求一次，结果共享（`url_bookmark_index` 映射）
- 超时/并发/重试次数可调（默认 10 秒 / 8 / 1）

### 3.3 判定规则（已写入文件头 docstring）

| 等级 | 触发条件 |
|---|---|
| `可用` ok | HTTP 2xx |
| `可疑` warn | 401/403/429、其它 4xx、5xx、451；**所有没拿到响应的网络层失败**；内网地址不可达 |
| `失效` bad | **只有** 404 / 410，以及重定向次数过多 |
| `跳过` skip | `chrome://`、`file://` 等非 HTTP 协议；含 `{{占位符}}` 的链接 |

**关键决策**：网络层失败（超时、DNS 失败、连接被拒、SSL 握手失败）一律降级为「可疑」而非「失效」。原因见 §5。

### 3.4 代理支持
- `system_proxy_map()` 读取注册表/环境变量代理（本机为 `127.0.0.1:7890`）
- `probe_proxy()` 用 `socket.create_connection` 探测端口存活
- 界面有「使用系统代理」勾选 + 「检测代理」按钮 + 实时状态显示
- `start_check()` 会预检代理，连不上时弹窗询问是否继续，避免整批误判

### 3.5 界面交互
- 进度条 + 实时统计（可用/可疑/失效/跳过）
- 表格默认按「失效 → 可疑 → 跳过 → 可用」分组排序，点表头切换排序
- 「只看失效/可疑」过滤
- 双击或用按钮在浏览器打开
- 复制全部失效链接到剪贴板
- 导出 CSV（UTF-8-BOM，Excel 直接打开不乱码）

### 3.6 打开链接
- **双击表格任意一行** → 用默认浏览器打开该收藏
- 或选中后点「打开选中」按钮（支持多选，逐个打开）
- 用 `identify_region == "cell"` 判断，双击表头/空白处不触发

> 注：**工具内已无任何复制功能**。曾实现过「批量复制失效链接 / 单击复制 / 右键复制菜单」
> 三套方案，按用户要求全部移除。需要 URL 时走「导出 CSV」。

界面按钮最终只剩 4 个：`开始检查` `停止` `导出 CSV` `打开选中`。

---

### 3.7 重复链接检测
- 表格新增「重复」列：`×2` = URL 完全相同，`≈2` = 归一化后相同
- 归一化 `normalize_url()` 忽略：协议（http/https）、`www.` 前缀、末尾斜杠、`#锚点`、大小写
- 查询参数**不**忽略（`?a=1` 与 `?a=2` 算不同页面）
- 「只看重复」勾选可筛出所有重复项（含近似重复）
- 状态栏显示「重复 N 组(多 M 条) · 近似重复 K 组」
- CSV 导出新增三列：重复次数 / 近似重复次数 / 归一化地址
- 本机 4 个配置文件实测共 229 条，**精确与近似重复均为 0**（功能为后续清理预留）

### 3.8 结果缓存
- 缓存文件：`收藏夹检查_cache.json`，与脚本同目录，**已加入 `.gitignore`**
- 启动程序**不联网**，只在状态栏显示「缓存 N 条 · 最近 时间」
- 点「开始检查」时：未过期缓存直接铺到表格（备注标 `[缓存]`），只有过期的才真正发请求
- 全部命中时**零网络请求**，秒出结果
- 缓存键 = `收藏夹路径 + URL`，换配置/换收藏夹文件不会串味
- 有效期由界面「复用缓存 N 天内」控制，默认 7 天；取消勾选则全量重测
- 检查结束后自动写回缓存
- CSV 导出新增「数据来源」列（`本次实测` / `缓存`）
- 缓存文件损坏或格式版本不符时静默忽略，不影响正常使用

缓存结构：
```json
{
  "version": 1,
  "saved_at": "2026-10-22 14:19:51",
  "entries": {
    "C:/Users/.../Default/Bookmarks	https://x.com/": {
      "level": "ok", "code": "200", "elapsed": "1.5 s",
      "note": "正常", "final_url": "https://x.com/",
      "name": "Twitter", "folder": "书签栏",
      "checked_at": 1792649962.94
    }
  }
}
```

---

## 4. 关键实现细节

### 4.1 增量插入而非整表重绘
`_insert_row()` 用 `bisect` 在 `self.order`（存书签下标的列表）里定位插入点，再用 `tree.insert(位置, ...)` 插到正确行。避免每来一条结果就重建整张表（214 条时明显卡顿）。

`self.order` 是唯一的顺序真相，`self.results[index]` 存结果，`iid` 直接用书签下标字符串。

### 4.2 Edge Bookmarks 格式
- 文件是 **CRLF + 3 空格缩进** 的 pretty-print JSON，无 BOM
- 读取时用 `utf-8-sig` 兼容
- `roots` 下除 `bookmark_bar`/`other`/`synced` 外，Edge 还有 `workspaces_v2`（工作区），解析时一并遍历
- 每个节点字段按字母序排列（`date_added`、`date_last_used`、`guid`、`id`、`name`、`show_icon`、`source`、`type`、`url`、`visit_count`）

### 4.3 SSL 处理
- 默认 **不校验证书**（`verify=False`）：收藏夹里常见自签/过期证书站点，开了会大面积误判
- 界面提供「校验证书」勾选，需要时可开

### 4.4 编码踩坑记录
- 本项目 `AGENTS.md` 要求中文对话与文档
- 用 bash heredoc 写含中文 + `\n` 的 Python 字符串时，反斜杠会被 bash 吞掉，导致 f-string 里出现真实换行 → `SyntaxError: unterminated f-string literal`
- **教训**：批量改代码时用 `chr(92) + 'n'` 构造转义，或用 `write` 工具直接写文件，不要用 heredoc 传含转义的代码

---

## 5. 验证结论（重要）

### 5.1 分类 bug 的实测证据
对比同一批链接「走代理 vs 直连」：

| 链接 | 代理 | 直连 |
|---|---|---|
| nic.eu.org | 200 | 200 |
| anyrouter.top/console | **200** | SSLError |
| epsonconnect.com | ConnectionError | ConnectTimeout |
| tools.lancely.tech | SSLError | ConnectionError |
| ai.ctacy.cc/profile | 404 | 404 |

`nic.eu.org`、`anyrouter.top` 第一轮被判「失效」，第二轮却返回 200 —— 证明超时/连接失败不能当失效。

### 5.2 修复前后对比（214 条，走代理）

| | 修复前 | 修复后 |
|---|---|---|
| 可用 | 176 | **180** |
| 可疑 | 18 | **29** |
| 失效 | 20 | **5** |

修复后 5 条失效全是真 404：
```
github.com/byhooi/daily_stock_analysis/settings/secrets/actions
ai.ctacy.cc/profile
www.szepi.net
beta.apple.com/sp/zh/betaprogram/guide
hero-sms.com/services
```

### 5.3 为什么「可疑」的链接浏览器能打开

实测排查结论（重要，避免误删）：

| 链接 | 实测结果 | 真实原因 |
|---|---|---|
| `linux.do` | 403，响应体含 `<title>Just a moment...</title>` | Cloudflare JS 挑战。补全 `sec-ch-ua`/`Sec-Fetch-*` 等浏览器头后仍 403，因为校验的是 TLS 指纹 + JS 执行结果 |
| `vaultwarden.byhooi.eu.org` | 缓存记录 SSL 失败，**重测 200** | 上次检测时临时故障（代理抖动），结果被缓存 7 天放大 |
| `muse.ai` | 400，跳转 `auth.muse.ai` | 需登录流程，无 cookie 直接访问被拒 |
| `data.xiaoyinsi.com` | 连续两次 SSLError | 该站握手异常或代理链路问题 |

**结论**：「可疑」只代表「程序判断不了」，不代表页面坏了。原因是 `requests` 不执行 JS、
不带登录 cookie、TLS 指纹不是真浏览器。这类必须人工双击确认。

缓解手段：取消「复用缓存」重跑、或把默认 TTL 从 7 天调小。

### 5.4 已跑过的测试
- 收藏夹解析：JSON 与 HTML 两种格式均正确
- 全量 214 条端到端检测（代理 / 直连两种模式）
- 停止按钮：中途停止后保留已完成结果，进度条正确
- 排序、过滤、CSV 导出
- 边界：`expired.badssl.com`（校验关闭→可用，开启→可疑）、`chrome://`（跳过）、内网 IP（可疑）、坏端口代理探测

### 5.5 环境事实
- Python 3.14.0，requests 2.33.1
- Windows 系统代理：`ProxyEnable=1`，`ProxyServer=127.0.0.1:7890`
- `ProxyOverride` 含 `192.168.*` 等内网段，所以内网地址自动绕过代理
- 出口 IP（走代理时）：150.230.205.65，地区 JP

---

## 6. 未完成：删除功能（已评估，主动放弃）

### 6.1 需求
在结果表里直接删除确认无效的收藏，免去手动去 Edge 收藏夹里找。

### 6.2 可行性结论：**技术上可行，但风险点未攻克**

删除操作本身很直接（定位节点、从 `children` 移除、可能需重排 `id`、更新父文件夹 `date_modified`）。真正的阻碍是 **checksum**：

- Edge 会校验 `Bookmarks` 里的 `checksum` 字段（当前值 `35dccff1fe260da4cd03354318baa3a9`）
- 算错可能导致 Edge 判定文件损坏而丢弃书签 —— 数据丢失风险

### 6.3 已尝试且失败的复刻路线
1. 按「节点字段顺序拼接 → MD5」：尝试 `id,name,url,type` 与 `url,id,name,type` 两种顺序，UTF-16LE / UTF-8 两种编码，含/不含 `synced`、`workspaces_v2` 根节点 —— **全部未命中**
2. 复刻 `base::JSONWriter` 紧凑序列化（key 字母序、无空格、非 ASCII 不转义）对 `{roots, version}` 求 MD5 —— **未命中**
3. 枚举 HTML 转义开关、ASCII 转义开关、`version` 取 1/`"1"`/省略、含/不含 `sync_metadata` 共 16 种组合 —— **全部未命中**

**结论**：还有未掌握的实现细节（可能是字段集合、id 重排规则，或 Edge 自己的变体）。

### 6.4 如果以后要做，推荐路线
1. **不写回 Edge 的 Bookmarks**，改为生成「待删除清单 + 操作指引」，人工在 Edge 里删
2. 或直接操作**导出的 HTML 收藏夹**（无 checksum 校验），改完再导入
3. 若坚持直接改 JSON：先在**副本**上验证「改完的 checksum 能被 Edge 接受」，方法是把改后的文件放回 `Default/` 目录、启动 Edge 看收藏是否还在 —— 务必先备份
4. 更彻底的思路：查 Chromium 源码 `components/bookmarks/browser/bookmark_codec.cc` 里 `BookmarkCodec::Encode` 的实际实现，而不是靠反推

---

## 7. 变更记录

### 本次新增：重复检测
- `normalize_url()`：URL 归一化
- `CheckResult` 新增 `duplicate` / `near_duplicate` 字段
- `start_check()` 里计算 `url_dup_count` / `url_near_count`
- 表格加「重复」列，`_dup_text()` 决定显示 `×N` 还是 `≈N`
- 新增「只看重复」筛选
- 已验证：真实重复（x.com 两条）、近似重复（www+http+斜杠变体）均正确识别

### 本次新增：结果缓存
- 常量 `CACHE_FILE` / `CACHE_VERSION`
- `_cache_key()` / `load_cache()` / `save_cache()` / `_format_timestamp()`
- `_refresh_cache_info()` / `_cache_ttl_seconds()` / `_cached_result()` / `_store_cache_entry()`
- `_apply_cached()`：把缓存结果铺到所有引用该 URL 的书签
- `start_check()` 改造：先填缓存，剩余才进线程池；全命中时直接 `_finish()`
- `CheckResult` 新增 `cached` 字段，`_update_summary()` 显示「其中缓存 N」
- 已验证：无缓存→全测、有缓存→零请求、关闭勾选→全测、TTL 过期→全测

### 复制功能：已实现后按要求移除
- 先后做过：按钮批量复制 → 单击行复制 → 右键菜单复制（三种格式）
- 用户最终确认「双击能打开就可以了，复制不需要」，已完整移除
- 移除内容：`_on_row_click`、`_row_result`、`_copy_one`、`_build_context_menu`、
  `_show_context_menu`、`_clicked_result`、`copy_clicked`、`copy_clicked_pair`、
  `open_clicked`、`copy_selected`、`copy_selected_names`、`copy_selected_pairs`、
  `_set_clipboard`、`clicked_iid`、`hint_var`、以及 `Ctrl+C` / 右键 / 单击绑定
- 「复制失效链接」按钮也已移除（用户再次确认不需要任何复制功能）
- 最终保留：「打开选中」按钮 + 双击打开
- 已回归验证：双击打开正常、全量 214 条检查正常、界面无残留控件

---

## 8. 后续可选项（未做）

- [ ] 把「网络层失败」再细分为「需重新确认」的单独一档，或加「重新检查选中项」按钮
- [ ] 导出时增加「只导出失效/可疑」选项
- [ ] 支持 Chrome / Firefox 收藏夹路径
- [ ] 清理 `__pycache__/` 并加进 `.gitignore`
- [ ] 提交 `收藏夹检查.pyw` 到 git（当前未提交）

---

## 9. 快速上手

```bash
cd D:/Documents/Github/Python
python 收藏夹检查.pyw
```

界面操作顺序：
1. 确认顶部「收藏夹文件」选对了配置（默认 `Default`）
2. 确认代理状态行显示 `当前代理：http://127.0.0.1:7890`（若代理软件没开，点「检测代理」会提示）
3. 点「开始检查」
4. 检查完成后表格自动按失效优先排序
5. 需要留档点「导出 CSV」
