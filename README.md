# GPT Researcher：使用 ChatGPT 套餐额度

协作开发、Agent 提交与合并规则见 [CONTRIBUTING.md](CONTRIBUTING.md)。


GPT Researcher 通过本地适配层接入 OpenAI 官方 Sign in with ChatGPT DevKit，使用授权账号的套餐能力调用公开的 Responses API。授权、权限检查、令牌刷新和响应完成检查由官方 SDK 处理。

不需要配置 OpenAI API Key。当前模型为 `gpt-6.1-sol`，搜索使用 DDGS，正文筛选使用关键词，不调用付费向量接口。

## 使用

在 ChatGPT 桌面端中的 Codex 对话里说：

> 用 GPT Researcher 调研……，比较不同来源，给出带链接的中文报告。

已安装上游 `gpt-researcher` Skill，并通过 Codex CLI 注册同名 MCP 服务。Skill 从安装后的下一轮对话加载。MCP 工具有 `quick_search`、`deep_research`、`write_report`、`get_research_sources`、`get_research_context`，另有本地只读工具 `chatgpt_plan_status`。

`deep_research` 收集资料后返回研究 ID；用这个 ID 调用 `write_report` 生成报告。研究 ID 和内容保存在本机 SQLite 中，服务空闲退出后仍可恢复。上游 MCP 的工具名称是 `deep_research`，其内部调用常规研究流程；CLI 的 `--deep` 才选择递归深度研究模式。

也可直接使用本地命令：

```powershell
& 'D:\Applications\GPTResearcher\gptr.cmd' status
& 'D:\Applications\GPTResearcher\gptr.cmd' research --query '你的调研问题'
& 'D:\Applications\GPTResearcher\gptr.cmd' research --deep --query '你的调研问题'
```

指定网页资料时，可以重复使用 `--source-url`；这种调用只读取指定来源，不额外扩展搜索：

```powershell
& 'D:\Applications\GPTResearcher\gptr.cmd' research --query '比较这些资料的观点' --source-url 'https://example.org/article'
```

CLI 默认把报告和来源记录保存到 `D:\Artifacts\GPTResearcher\reports`。`--output` 可指定新文件路径；已有报告不会被覆盖。MCP 返回报告内容，由调用方保存。

## 当前配置

| 项目 | 配置 |
| --- | --- |
| GPT Researcher | 0.16.1 |
| MCP | assafelovic/gptr-mcp，固定提交见 upstream.json |
| 运行环境 | Python 3.14、Node.js 24 |
| 模型 | fast / smart / strategic 均为 `openai:gpt-6.1-sol` |
| 搜索 | DuckDuckGo 检索器使用 DDGS；DDGS 可调用多个公开搜索引擎 |
| 常规研究 | 2 个规划查询，每个查询最多 3 条结果 |
| 递归深度研究 | 深度 2、广度 2、并发 1 |
| 报告 | 中文，默认目标 800 词；可在研究问题及报告指令中约定篇幅 |
| MCP 超时 | 启动 90 秒，工具调用 1800 秒 |

实际配置在 `D:\AppData\GPTResearcher\research-config.json`；仓库的 `research-config.example.json` 是配置样例。

## 检索与额度的边界

- 模型使用官方 ChatGPT 套餐授权路线。没有测量某个 Codex 用量窗口减少了多少；具体额度和限制由 OpenAI 账号侧决定。达到额度限制时会报错，不转用其他付费模型。
- GPT Researcher 日志中的美元成本是它按 API 价格计算的估算值，不能作为这条套餐路线的扣费凭证。
- 免费搜索引擎可能限流或返回空结果，部分中文查询已观察到这种情况。需要更完整覆盖时，应组合平台专用检索、GitHub、博客和已知来源链接。
- GPT Researcher 不会自动继承浏览器 Cookie。小红书、知乎等登录态内容仍通过各平台已配置的获取工具采集；此处的安装不代表所有社交平台都可由 GPT Researcher 直接访问。
- 当前适配处理文本研究任务，不接入图片生成、模型侧工具调用或付费向量服务。官方 DevKit 的预览范围和账号资格以官方说明为准。

## 本机网络兼容

本机代理会将公网域名解析到 `198.18.0.0/15`，这会触发 GPT Researcher 的内网地址保护。`proxy_dns.py` 只为 URL 校验模块处理这类域名：通过 Google DNS over HTTPS 复核 A / AAAA 记录，确认均为公网地址后才通过。实际 HTTP 连接仍沿用系统代理。

该处理不会修改系统 DNS，也不会关闭 URL 保护。内网、回环、元数据地址、本地文件协议、直接输入的 Fake-IP 地址仍被拒绝；公共 DNS 校验失败时同样拒绝。与上游一样，校验和实际连接之间仍存在 DNS 重绑定时间窗口，这不是面向不受信任用户部署的公共服务。

## 文件与账号

| 用途 | 路径 |
| --- | --- |
| 适配源码 | `D:\Projects\GPTResearcherChatGPT` |
| Python、官方 SDK、上游 MCP | `D:\Applications\GPTResearcher` |
| 配置、工作数据、加密授权 | `D:\AppData\GPTResearcher` |
| 下载和运行缓存 | `D:\Caches\GPTResearcher` |
| 安装记录、验收、报告 | `D:\Artifacts\GPTResearcher` |
| Skill 实体 | `D:\AppData\Codex\skills\gpt-researcher` |

授权数据使用 Windows 当前用户 DPAPI 加密，目录访问限定为当前用户和 SYSTEM。账号令牌由 SDK 内部使用，不经过模型适配层的消息管道，不写入源码仓库。源码私有仓库仅保存适配代码和非敏感配置样例。

C 盘仅保留 Codex 必需的配置文件和指向 D 盘 Skill 的目录入口；沿用已有 Python、Node.js、PowerShell 安装。

## 验证与维护

MCP 现通过 `http://127.0.0.1:19782/mcp/gpt-researcher` 共享一份后端，空闲 10 分钟后回收，活动或排队调用受到保护。研究操作串行执行；完成的对象按需从 `D:\AppData\GPTResearcher\mcp-state.sqlite3` 恢复，不在内存中无限累积。状态库上限为 256 MiB，满额时保留既有内容并拒绝新写入，不自动删除成果。`GPTR_MCP_STATE` 仅用于验收时指定隔离状态库。

共享服务的安装、兼容补丁、恢复边界与管理命令见 `D:\Projects\DeveloperGovernance\MCP.md`。共享入口保留原工具名，暂不透传上游资源 URI 和提示模板。

完整 MCP 验收已通过：快速搜索返回 5 条结果，研究读取 3 个 Python 官方文档页面，使用套餐完成 3 次模型调用，生成 797 字符的中文报告。12 项适配和 URL 校验测试通过。中文长查询的独立测试没有检索到来源，保留为当前搜索后端的已知限制。

官方授权探针：`D:\Artifacts\GPTResearcher\verification\chatgpt-plan-probe.json`。

GPT Researcher 模型调用探针：`D:\Artifacts\GPTResearcher\verification\integration-probe.json`。

完整 MCP 验收记录和报告分别为 `mcp-research-receipt.json`、`mcp-research-report.md`，位于同一目录。只有记录中的 `complete: true` 才表示搜索、来源读取、报告和套餐调用均已通过。

```powershell
Set-Location 'D:\Projects\GPTResearcherChatGPT'
& 'D:\Applications\GPTResearcher\venv\Scripts\python.exe' -m unittest -v test_provider.py test_proxy_dns.py
& 'D:\Applications\GPTResearcher\venv\Scripts\python.exe' -u verify_mcp.py --research
```

`install-runtime.ps1` 安装 Python 依赖并打包官方 SDK；SDK 源码构建来自已核验的 `D:\Quarantine\GPTResearcherVerification\sign-in-with-chatgpt-devkit`。重新部署到其他机器时，需要按 `upstream.json` 恢复对应 SDK 和上游 MCP 源码，并重新完成该机器上的账号授权。Python 完整依赖清单保存在安装记录目录的 `requirements.lock.txt`，SDK 依赖由运行目录中的 `package-lock.json` 记录。

停用 MCP 可运行 `codex mcp remove gpt-researcher`。这不会删除本地报告或账号授权；撤销授权应通过 OpenAI 账号的应用授权管理完成。

## 原始项目和官方文档

- [GPT Researcher](https://github.com/assafelovic/gpt-researcher)
- [GPT Researcher MCP](https://github.com/assafelovic/gptr-mcp)
- [OpenAI Sign in with ChatGPT DevKit](https://github.com/openai/sign-in-with-chatgpt-devkit)
- [官方套餐授权说明](https://developers.openai.com/siwc/token-sharing-open-source)
- [Google DNS over HTTPS JSON API](https://developers.google.com/speed/public-dns/docs/doh/json)
