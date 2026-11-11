# Wuwa Tappo 自动开宝箱助手

给鸣潮桌宠 [Wuwa Tappo]（`D:\WuwaTappo\WuwaTappo.exe`）用的零依赖小工具：通过 WebView2 的调试端口（CDP）在页面里做**真实可信的点击**，到点自动开宝箱。

## 能做什么

- **自动开宝箱**：桌宠每累计 30 分钟活跃时间生成 1 个宝箱（最多 2 个槽位），工具轮询 `user/me` 发现可开启就点开页面里真实的宝箱按钮，等掉落动画播完，记录开到了什么（角色皮肤/稀有度）。每次开箱消耗 1,000 字符数。
- **状态查询**：两个槽位的倒计时 + 当前字符余额（= `total_click_count - total_click_consume`）。
- **掉线自愈**：watch 模式下 CDP 断开会自动重连。

## 不能做什么（重要）

- **自动刷字符数做不到**：桌宠的点击/按键计数走 Rust 原生钩子，会过滤掉程序注入的事件。实测三种方式**全都不计数**：
  - `SendInput` 模拟按键/鼠标（150 次按键、20 次点击）
  - CDP `Input.dispatchKeyEvent` / `Input.dispatchMouseEvent`
  - 向 `DesktopCatInput` 窗口 `PostMessage` 鼠标消息
  期间余额只在用户真实打字时才涨。
- 直接伪造 `api/frontend/chests/open` 也绕不过去（服务端有 `70003 客户端点击数异常` 之类校验），且有封号风险，因此没有实现。

一句话：**宝箱可以全自动，字符数还得靠你真敲键盘**。

## 前置：给桌宠开调试端口（一次性，需要管理员）

策略键：`HKLM\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments`
值名必须是**裸文件名** `WuwaTappo.exe`（不是全路径！），值为 `--remote-debugging-port=9222`——WebView2 会把它追加上去，绕过 Tauri 自己写死的启动参数。

1. 右键开始菜单 → 「终端(管理员)」。
2. 在管理员窗口里执行：
   ```
   C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\fix-cdp.cmd
   ```
   它会写入策略、重启桌宠、并探测端口。
3. 看到 `{"Browser":"Edg/...","webSocketDebuggerUrl":"ws://127.0.0.1:9222/..."}` 就成功了。

取消：管理员窗口执行 `reg delete "HKLM\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments" /v WuwaTappo.exe /f`。

## 用法

```bat
cd /d "C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa"

D:\nodejs\node.exe wuwa-bot.mjs state    :: 看余额和两个槽位倒计时
D:\nodejs\node.exe wuwa-bot.mjs open     :: 立刻尝试开一次
D:\nodejs\node.exe wuwa-bot.mjs watch    :: 常驻，到点自动开（推荐）
```

- 常驻：双击 `start-bot.cmd`（有控制台窗口，输出同时写 `run.log`）。
- 开机自启（管理员窗口执行一次）：
  ```bat
  schtasks /create /tn "WuwaBot" /tr "cmd /c cd /d C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa && \"D:\nodejs\node.exe\" wuwa-bot.mjs watch >> run.log 2>&1" /sc onlogon /f
  ```
  删除：`schtasks /delete /tn "WuwaBot" /f`
- 日志：`wuwa-bot.log`（程序自己写）、`run.log`（cmd 启动时的控制台输出）。

## 参数

| 参数 | 说明 |
| --- | --- |
| `--interval 20` | 轮询间隔（秒），最小 10 |
| `--dry` | 只找宝箱不点击（调试用） |
| `--log 文件` | 自定义日志文件 |

环境变量 `WUWA_CDP_PORT` 可改调试端口（默认 9222）。

## 文件

| 文件 | 作用 |
| --- | --- |
| `wuwa-bot.mjs` | 主程序（state / open / watch） |
| `cdp.mjs` | 零依赖 CDP 客户端（HTTP + WebSocket） |
| `fix-cdp.cmd` | 一次性配置调试端口并重启桌宠（需管理员） |
| `start-bot.cmd` | 启动常驻模式 |
| `probe.mjs` | 侦察脚本：打印页面 DOM、storage、按钮清单 |

## 原理速记

- 桌宠是 Tauri + WebView2，主页面 `#/`，另有 `#/panel`、`#/login`、`#/about`、`#/toast` 等隐藏页。
- 状态接口：`GET https://api-mc-wuwatappo.kurogames-global.com/api/frontend/user/me`，返回 `total_click_count`、`total_click_consume`、`left_treasure_chest`、`right_treasure_chest`（毫秒时间戳）。
- 鉴权：cookie `kuro_infoToken` + 请求头 `Authorization: Bearer <token>` + `X-BLM-CID`（localStorage `KURO_YCK_REQ_CID`）。脚本在页面里发同源请求，借用 App 自己的登录态，不用自己存 token。
- 宝箱就绪时 DOM 里出现 `.chest-reward-popup-layer .reward-anchor--left/--right > button.reward-btn`，点击后走 App 自己的 `jsonpClient.post('api/frontend/chests/open')`；掉落动画约 2.5 秒后自动消失，无需点确定。
- 稀有度：Common 90% / Uncommon 9.5% / Rare 0.49% / Epic 0.01%。