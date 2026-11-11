# QQ 自动回复 · 使用说明

> 一句话：**双击一个文件把 NapCat 拉起来，DSH 开着，大号给小号发消息就有人回。**

- 小号（机器人号）：`1561846322`　昵称 `＼(Δ’)／`
- 大号（你）：`1831024112`　昵称 `꧁春榆꧂`
- 写在：2026-11-05

---

## 一、启动（已设成登录自启，通常不用管）

**登录 Windows 后约 20 秒会自动弹出来**（QQ 登录窗 + 黑色 NapCat 窗口），什么都不用点。

想手动启动/自启没生效时，双击这个文件：

```
D:\NapCat\QQ933\启动NapCat.cmd
```

会出现两样东西，两样都要留着：

1. QQ 登录窗（小号已登录的状态）
2. 一个黑色命令行窗口 —— **这就是 NapCat 本体，关掉它小号就掉线**

看到黑窗口里滚出 `OneBot v11` 相关字样就说明起来了。然后去 DSH 里看「设置 → QQ」，或者直接发条消息试。

> 自启文件：`C:\Users\18310\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\NapCat-Autostart.cmd`
> 它等 20 秒后调用 `D:\NapCat\QQ933\start-napcat.cmd`（原启动脚本的纯 ASCII 版，避免中文路径在启动项里出问题）。

---

## 二、它到底怎么跑的（一张图看懂）

```
你大号 ──QQ消息──▶ Tencent 服务器 ──▶ QQ(NapCat 副本) ──OneBot WS──▶ DSH 插件 ──▶ Agent 回复
                                        ws://127.0.0.1:3001
```

- **NapCat**：跑在 `D:\NapCat\QQ933` 里的 QQ 副本（9.9.33.52230 + 注入），负责收消息、发消息。
- **DSH 插件**（`dsh-qq-onebot`）：连上 NapCat 的 WebSocket，把 QQ 消息变成 DSH 会话，把回复发回去。
- **所以两个都得活着**：NapCat 黑窗口 + DSH 主程序。缺一个就不回。

---

## 三、日常怎么用

| 场景 | 做法 |
| --- | --- |
| 私聊 | 大号直接给小号发，几秒内回 |
| 群聊 | 拉小号进群，**@ 它**才回（默认不插嘴） |
| 让它干活 | 它能用 DSH 的全部工具（读写文件、跑命令、搜网页）；需要授权的操作会发到 QQ，你回「通过」/「拒绝」 |
| 想改人设 | DSH 里「设置 → QQ」→ 人设；或改 `C:\Users\18310\.dsh\dsh-qq\settings.json` 里的 `persona` |
| 不想被吵 | 设置里开 `sleepMode`（默认 00:00–08:00 静默），现在是**关**的 |

> 主动说话：安静 20 分钟后它可能自己找你（每天最多 6 次，23:00–08:00 不打扰）。

---

## 四、文件都在哪

| 东西 | 路径 |
| --- | --- |
| **启动脚本** | `D:\NapCat\QQ933\启动NapCat.cmd` |
| QQ 副本目录 | `D:\NapCat\QQ933`（QQ.exe + NapCat 文件） |
| NapCat 配置（WS 端口/token） | `D:\NapCat\QQ933\config\onebot11_1561846322.json` |
| NapCat 网页管理台 | `http://127.0.0.1:6099`（token 见 `D:\NapCat\QQ933\config\webui.json`） |
| OneBot WebSocket | `ws://127.0.0.1:3001`，token `83bd6d91938f016467dae9ce57e81c2a` |
| 插件设置 | `C:\Users\18310\.dsh\dsh-qq\settings.json` |
| 插件配置（模型/开关） | `C:\Users\18310\.dsh\profiles\desktop\cordis.patch.yml` |
| 插件日志（排错看这个） | `C:\Users\18310\.dsh\profiles\desktop\logs\dsh-qq-2026-11-05.log` |
| 设置服务（本地） | `http://127.0.0.1:34569/api/dsh-qq` |

---

## 五、常见问题

### 1）发消息过去，它回一句 `⚠️ prompt variable "{{model}}" ...`

插件给会话建的 agent 没带模型，提示词渲染就失败了。检查 `C:\Users\18310\.dsh\profiles\desktop\cordis.patch.yml` 末尾是否有这段（少了就补上，存盘后 DSH 会自动热重载插件，不用重启）：

```yaml
- id: dsh-qq
  name: dsh-qq-onebot
  config:
    provider: deepseek-account
    model: deepseek-flash
```

### 2）完全不回、日志里连「收到消息」都没有

按顺序查：

1. NapCat 黑窗口还开着吗？（关了 = 掉线）
2. DSH 主程序开着吗？
3. 发消息的号在不在白名单里？现在只有大号 `1831024112`。
4. 是不是落在睡眠时段？（现在 `sleepMode: false`，不受影响）
5. 看日志最后几行：`C:\Users\18310\.dsh\profiles\desktop\logs\dsh-qq-2026-11-05.log`

### 3）日志里反复出现 `token验证失败` / 连上又被踢

NapCat 那边 token 和插件这边不一致，或插件没拿到新 token。改完设置后调用一次重连：

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:34569/api/dsh-qq/reconnect
```

### 4）想再加一个人能私聊它

```powershell
$body = '{"patch":{"privateAllow":["1831024112","另一个QQ号"]}}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:34569/api/dsh-qq/settings -ContentType 'application/json' -Body $body
```

（`privateMode` 是 `allowlist`，不在名单里的人发消息会被无视——这是故意的，防止陌生人指挥你电脑上的 agent。）

### 5）小号掉登录了

双击 `D:\NapCat\QQ933\启动NapCat.cmd`，在弹出的 QQ 窗里重新扫码/登录小号即可。

### 6）电脑重启后要做什么

**已经是登录自启了，正常情况下什么都不用点**：登录 Windows 后约 20 秒自动起。

自启文件：`C:\Users\18310\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup\NapCat-Autostart.cmd`。想临时跳过就把它改名；自启被安全软件拦了，还是手动双击 `D:\NapCat\QQ933\启动NapCat.cmd`。

---

## 六、注意事项

- **必须用单独的小号**。挂着 NapCat 的 QQ 客户端有被腾讯风控的可能，别拿大号冒这个险。
- 别把 QQ 号随便给别人加白名单：能私聊它，就等于能指挥跑在你这台电脑上的 agent。
- 这套东西依赖本机端口（9222 之外的 3001/6099/34569），开了会拦截本机端口的「安全软件」可能会捣乱。

---

## 七、想彻底卸掉

1. 关掉黑窗口，退出 QQ 副本
2. DSH 里卸载插件：`dsh plugin --profile desktop remove dsh-qq-onebot`（或插件市场里删）
3. 想清干净就把 `D:\NapCat` 整个删掉，再删 `C:\Users\18310\.dsh\dsh-qq\`

---

## 怎么做到「登录一次，以后不用扫码」（2026-11-08 更新）

1. **第一次登录时，在 QQ 登录窗口把「自动登录」勾上**（窗口下方的小方框），再确认登录。这一步是 QQ 自己记登录态，不勾的话每次都会重新要二维码。
2. 以后启动用 `D:\NapCat\QQ933\start-napcat.cmd`（已经改成带账号 1561846322 的快速登录模式）。它会先尝试用上次的登录态直接进去，进不去才显示二维码。
3. 万一快速登录失败（比如账号被踢），双击 `D:\NapCat\QQ933\start-napcat-qr.cmd`，走扫码登录，扫完记得再勾一次「自动登录」。
4. 不要用任务管理器强杀 QQ，也不要在手机/另一台电脑同时登这个号——被踢一次，登录态就废了，又得扫码。
5. 守护脚本 `watch-napcat.cmd` 现在只在「QQ 进程真的没了」时才重启，避免双开互踢。
