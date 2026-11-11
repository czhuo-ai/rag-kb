# 鸣潮桌宠（Wuwa Tappo）· 自动开宝箱 使用说明

> 一句话：**双击一个文件，它就在后台帮你守着宝箱，到点自己领。**

- 工具目录：`C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\`
- 桌宠：`D:\WuwaTappo\WuwaTappo.exe`
- 写在：2026-11-05

---

## 一、它做什么

桌宠每累计用 30 分钟攒 1 个宝箱（最多存 2 个，左右两个槽各自计时）。宝箱到期后页面会出现一个「开启」按钮，点一下扣 1000 字符数、随机给皮肤碎片。

这个工具就是替你盯着：**宝箱一到点，自动点开、领掉、等掉落动画放完。**

做不到的：**字符数不会自己涨**。桌宠的点击/按键计数走 Windows 底层钩子，程序模拟的键鼠一律不计，只有你真手敲键盘才算（我试过 SendInput、CDP 注入、PostMessage 三种，全被过滤）。

---

## 二、日常使用（3 步）

1. 把桌宠开着（`D:\WuwaTappo\WuwaTappo.exe`，挂在桌面上就行）。
2. **双击：**
   ```
   C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\启动自动开箱.cmd
   ```
   弹出「✅ 已启动（进程 xxxx）」就完事了，提示关掉即可。
3. 就这样。**不用开 DSH，也不用一直开着那个文件夹。**

| 想干嘛 | 双击这个（同一目录下） |
| --- | --- |
| 开始守宝箱 | `启动自动开箱.cmd` |
| 关掉 | `停止自动开箱.cmd` |
| 看余额和倒计时 | `查看宝箱状态.cmd` |
| 登录 Windows 自动启动 | `设置开机自启.cmd`（点一次就够） |

完整路径写开就是：

- 启动：`C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\启动自动开箱.cmd`
- 停止：`C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\停止自动开箱.cmd`
- 状态：`C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\查看宝箱状态.cmd`

---

## 三、前提条件（不满足就不干活）

1. **桌宠必须开着**——它读的是桌宠页面里的状态。
2. **调试端口 9222 必须开着**——一次性配好，重装桌宠后要重配：
   右键开始菜单 → 「终端(管理员)」→ 把
   `C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\fix-cdp.cmd`
   拖进去回车，看到输出里有 `webSocketDebuggerUrl` 就成了。
3. **电脑别睡眠**（睡眠期间不领；醒来会补，因为最多存 2 个）。

---

## 四、文件都在哪

| 东西 | 路径 |
| --- | --- |
| **启动 / 停止 / 状态 / 自启** | `...\default-workspace\wuwa\` 下四个 `.cmd`（`...` = `C:\Users\18310\Documents\deepseek-harness`） |
| 程序本体 | `...\wuwa\wuwa-bot.mjs`（别动） |
| 启动器（.cmd 背后调的） | `...\wuwa\start-bot.ps1` / `stop-bot.ps1` |
| 运行日志 | `...\wuwa\wuwa-bot.log`（每轮一行）、`...\wuwa\run.log`（启动日志） |
| 记录运行中的 pid | `...\wuwa\bot.pid` |
| 调试端口配置脚本 | `...\wuwa\fix-cdp.cmd`（管理员运行，一次性） |
| 旧版教程（同样内容） | `...\wuwa\使用教程.md` / `使用教程.html` |

---

## 五、怎么确认它真在干活

双击 `查看宝箱状态.cmd`，会打印类似：

```
[02:18:07] 字符余额 8231（累计 318231，已用 310000）
[02:18:07]   左槽：⏳ 5分28秒后
[02:18:07]   右槽：⏳ 5分30秒后
```

到点领到东西时，日志里会出现：

```
🎁 得到 role_1208_1005.png（common）
```

---

## 六、常见问题

**1）弹「没连上桌宠的调试端口（127.0.0.1:9222）」**
- 桌宠没开 → 先开桌宠再启动。
- 桌宠开着还报错 → 重装过桌宠，按上面「三、前提条件」第 2 条重跑 `fix-cdp.cmd`。

**2）双击启动后没反应 / 一闪而过**
用管理员终端手动跑一次看报错：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\Users\18310\Documents\deepseek-harness\default-workspace\wuwa\start-bot.ps1"
```

**3）为什么字符余额不涨？**
见开头：程序模拟的输入不算数，只能真人敲键盘。宝箱全自动，字符数得你自己来。

**4）宝箱会不会一直攒？**
不会，最多 2 个，满了就不再生成。所以别长期不开机。

**5）会不会封号？**
它做的事是「在桌宠自己的界面里点它自己的宝箱按钮」，没改数据、没伪造计数、没暴力刷接口。但自动化终归有风险，介意就手动开。

**6）一次能领几个？**
两个槽独立，各领各的，每次各扣 1000 字符。

**7）想彻底卸载**

1. 双击 `停止自动开箱.cmd`
2. 删掉 `...\wuwa` 整个文件夹
3. （可选，管理员终端）关掉调试端口：
   `reg delete "HKLM\Software\Policies\Microsoft\Edge\WebView2\AdditionalBrowserArguments" /v WuwaTappo.exe /f`

---

## 七、原理（可以跳过）

桌宠是 Tauri + WebView2 做的网页应用。给它开 Chrome 调试端口（9222）后，程序能直接读页面、点页面按钮，跟人手点一样，只是快一点。

- 余额 / 倒计时：读 `api/frontend/user/me`（借用桌宠自己的登录态）
- 宝箱按钮：页面里的 `.reward-anchor--left/--right > button.reward-btn`
- 点击：CDP 发真实鼠标事件（`isTrusted = true`，Vue 正常响应）
- 领奖结果：抓 `chests/open` 的返回，写进日志

稀有度概率：Common 90% / Uncommon 9.5% / Rare 0.49% / Epic 0.01%。
