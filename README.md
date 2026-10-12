# BiliHelper

B站会员购(show.bilibili.com)演出抢票脚本: 演出售罄后持续监控余票(捡漏回流票), 出现可购票档时自动完成 选场次 → 选票档 → 加数量, 进入确认订单页; 可自动勾选实名观演人, 可选自动创建订单(支付需人工完成)。

> **适用说明**: 本项目面向**实名制观演人(一人一票)**的会员购演出; 目前仅在「未来有你2026」演出上实际验证过, 其他演出不保证成功。

> 本项目仅用于个人学习与亲友购票, 请遵守平台规则, 切勿用于商业代抢、倒卖。使用风险详见文末「免责声明」。

## 功能特性

- **余票监控**: 循环请求演出详情接口, 实时监控各场次 / 票档的余票状态
- **自动抢票**: 命中余票后自动选场次、选票档、加数量, 一路进入确认订单页
- **自动勾选观演人**: 按配置的姓名自动勾选实名观演人, 并自动勾选服务条款
- **半自动下单**: `auto_pay=true` 时自动点击「下一步支付」创建待支付订单, 并通过系统通知提醒(macOS)
- **风控友好**: 轮询间隔随机波动 + 周期性随机长停顿, 模拟人工节奏
- **本地登录**: 首次运行扫码登录, 登录状态只保存在本地 `cookies.pkl`, 不经过任何第三方
- **代理支持**: 可配置本地代理, 代理不可用时自动回退直连

## 工作原理

1. 通过会员购演出详情接口获取场次与票档的实时余票状态;
2. 命中目标票档后, 驱动 Chrome 打开演出详情页, 自动完成选场次、选票档、加数量等操作, 进入确认订单页;
3. 在确认订单页自动勾选实名观演人, 并按配置决定是否自动创建订单;
4. 支付环节需人工在浏览器中完成。

## 环境准备

- Python 3.9+(开发环境 3.12)
- Google Chrome 浏览器
- Git(可选: 没有 Git 也可以在仓库页面下载 ZIP)

除「获取代码」外, 后续步骤都需要**在项目文件夹(BiliHelper)内**的终端里执行: macOS / Linux 使用「终端」, Windows 使用 PowerShell 或 CMD。

### 1. 获取代码

macOS / Linux(终端):

```bash
git clone https://github.com/JerryLiiiiii/BiliHelper
cd BiliHelper
```

Windows(PowerShell / CMD):

```powershell
git clone https://github.com/JerryLiiiiii/BiliHelper
cd BiliHelper
```

> - 没有安装 Git: 在仓库页面点「Code → Download ZIP」下载并解压, 再进入解压出的文件夹, 后续步骤完全一样。

### 2. 创建并激活虚拟环境(推荐)

虚拟环境会把本项目依赖装进项目文件夹, 不会污染你电脑的全局 Python 环境; 之后**每次使用脚本前, 先激活再运行**。

macOS:

```bash
# macOS 自带的 Python(由 Xcode / 命令行工具提供)创建虚拟环境可能报错,
# 推荐先用 Homebrew 安装独立的 Python 3.11, 再用它创建虚拟环境
brew install python@3.11
python3.11 -m venv .venv
source .venv/bin/activate
```

> - 还没有 Homebrew? 先安装: 打开 https://brew.sh/zh-cn/ 按页面提示执行安装命令(安装过程会提示安装 Xcode Command Line Tools, 按提示完成即可);
> - 不想用 Homebrew 也可以: 从 python.org 下载 Python 3.11 官方安装包, 装完后同样执行 `python3.11 -m venv .venv`。

Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

> Ubuntu / Debian 若提示缺少 venv 模块(如 `ensurepip is not available`), 先执行 `sudo apt update && sudo apt install -y python3-venv python3-pip` 再重试。

Windows(PowerShell):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Windows(CMD):

```bat
python -m venv .venv
.venv\Scripts\activate.bat
```

> - 激活成功后, 命令行提示符前面会出现 `(.venv)` 字样;
> - Windows 若提示找不到 `python` 命令: 可改用 `py -m venv .venv` 创建虚拟环境(Windows 自带 py 启动器); 激活后直接运行 `python main.py` 即可, 或重装 Python 时勾选「Add python.exe to PATH」;
> - PowerShell 若提示「禁止运行脚本」, 可改用上面的 CMD 方式, 或先执行 `Set-ExecutionPolicy -Scope Process Bypass` 再激活;
> - 需要退出虚拟环境时, 执行 `deactivate`。

### 3. 安装依赖

```bash
pip install -r requirements.txt
```

> - 国内网络安装缓慢时, 可改用 `pip install -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple`;
> - 关于浏览器驱动: 默认**无需手动下载**, 依赖中的 Selenium(≥4.6) 会自动匹配本机 Chrome; 如需手动指定, 见「浏览器驱动说明」。

## 快速开始

1. 按「环境准备」完成三件事: 克隆并进入项目文件夹 → 创建并激活虚拟环境 → 安装依赖(之后每次运行脚本前, 记得先激活虚拟环境);
2. 创建配置文件:
   `config.json.example` 是仓库提供的**配置模板**, 请复制一份为 `config.json` 再修改(不要直接在模板文件上改, 拉取更新时会被覆盖):
   - macOS / Linux: `cp config.json.example config.json`
   - Windows: `copy config.json.example config.json`
3. 打开 `config.json`, 参照注释填写演出 ID、场次 / 票档优先级、票数、观演人姓名等;
   浏览器驱动默认不用管(自动匹配); 如果你手动下载了驱动, 请把驱动文件**放进项目文件夹内**, 并把 `driver_path` 填成**相对路径**: macOS / Linux 填 `"./chromedriver"`, Windows 填 `"./chromedriver.exe"`(详见「浏览器驱动说明」);
4. 确认终端位于项目文件夹、且虚拟环境已激活, 然后运行:

```bash
python main.py
```

5. 首次运行会自动打开浏览器并弹出登录二维码, 使用「哔哩哔哩」APP 扫码登录(登录状态保存到 `cookies.pkl`, 之后无需重复登录);
6. 脚本开始监控余票, 抢到后进入确认订单页, 按提示在浏览器中完成支付。

### 如何获取演出 ID(item_id)

打开目标演出的详情页, 网址形如:

```
https://show.bilibili.com/platform/detail.html?id=1234567
```

`id=` 后面的数字即为 `item_id`。

## 浏览器驱动说明(可选)

默认**无需手动下载驱动**: Selenium(≥4.6) 会在首次运行时自动下载与本机 Chrome 匹配的 ChromeDriver, 保持 `driver_path` 为空即可。

只有自动匹配失败、或网络无法访问驱动下载源时, 才需要手动指定。手动下载前请先确认三件事: **内核、版本、架构**。

### 1. 确认内核、版本、架构

| 要确认的 | 怎么查 |
| --- | --- |
| 内核 | 本项目只支持 **Google Chrome**(Chromium 内核); 其他浏览器(Edge、Firefox、Safari 等)不在支持范围 |
| 版本 | Chrome 右上角菜单 → 帮助 → 关于 Google Chrome, 或在地址栏访问 `chrome://version`, 记下版本号(如 `141.0.7390.55`); **驱动的大版本必须与 Chrome 大版本一致**(如 141.x 的 Chrome 配 141.x 的驱动) |
| 架构 | macOS: 左上角苹果菜单 → 关于本机 → 「芯片/处理器」(Apple M 系列 = arm64, Intel = x64); Windows: 设置 → 系统 → 关于 → 「系统类型」(一般为 x64); Linux: 终端执行 `uname -m`(`x86_64` = x64, `aarch64` = arm64) |

### 2. 下载对应驱动

官方下载页(Chrome for Testing): https://googlechromelabs.github.io/chrome-for-testing/

- 在 Stable 列表里找到与你 Chrome 大版本一致的版本号;
- 下载对应平台的 `chromedriver` 压缩包:
  - macOS(Apple 芯片): `mac-arm64`
  - macOS(Intel): `mac-x64`
  - Windows(64 位): `win64`
  - Linux: `linux64`

> 下载页偶尔不稳定, 多刷新几次或换个网络环境再试。

### 3. 放进项目文件夹, 配置相对路径

- 解压后, 把里面的 `chromedriver`(Windows 是 `chromedriver.exe`)**直接放进项目文件夹内**(与 `main.py` 同级);
- 在 `config.json` 里把 `driver_path` 填写为**相对路径**:
  - macOS / Linux: `"driver_path": "./chromedriver"`
  - Windows: `"driver_path": "./chromedriver.exe"`
- macOS / Linux 首次使用前, 在项目文件夹内执行 `chmod +x ./chromedriver` 赋予执行权限;
- macOS 若提示「无法验证开发者」, 先执行 `xattr -d com.apple.quarantine ./chromedriver` 再运行。

> 相对路径是相对「运行脚本时所在的目录」; 只要按本文档在项目文件夹内运行 `python main.py`, 这样填就不会出错。之后 Chrome 自动升级导致驱动失效时, 重新下载匹配版本, 或把 `driver_path` 留空交回自动匹配。

## 配置说明(config.json)

| 字段 | 说明 |
| --- | --- |
| item_id | 演出 ID, 取自详情页网址 `detail.html?id=` 后面的数字 |
| sess | 场次优先级: 序号从 1 开始(按详情页场次从上到下排), 数组里排在前面的优先, 例 `[1,2]` |
| price | 票档优先级: 序号从 1 开始(按详情页票档顺序, 通常价格从低到高排), 数组里排在前面的优先, 例 `[1,2]` |
| ticket_num | 购买票数, 需与勾选的实名观演人数量一致(一人一票) |
| buyer_names | 需要自动勾选的实名观演人姓名, 须与会员购中保存的姓名完全一致; 留空 `[]` 表示保持页面默认勾选 |
| auto_pay | true=自动点击「下一步支付」创建订单(支付仍需人工); false=停在确认页手动处理 |
| poll_interval | 余票轮询间隔(秒), 建议 0.5~1.5 |
| jitter | 轮询间隔的随机波动上限(秒), 用于模拟人工节奏、降低被风控的概率 |
| proxy | 可选: 本地代理地址, 如 `http://127.0.0.1:7890`; 留空=直连 |
| driver_path | 可选: chromedriver 可执行文件路径; 留空或路径无效时由 Selenium 自动匹配 |

配置文件中的 `comment` 字段为说明性注释, 不影响运行。

## 网络与代理

脚本对网络的处理规则:

- **默认不使用代理**: `proxy` 留空时, 接口请求与浏览器**都强制直连**(会忽略系统里的代理 / VPN 设置); 多数网络环境下直接这样使用即可;
- **直连不稳定时再配代理**: 如果直连 show.bilibili.com 经常超时、加载缓慢(部分宽带、校园网会出现), 先在本机打开代理软件(Clash、V2Ray 等), 再把它的 HTTP 代理地址填到 `proxy`, 例如 `"proxy": "http://127.0.0.1:7890"`; 填写后接口请求和浏览器都会走这个代理, 保证网络出口一致;
- **端口以你的代理软件为准**: 在代理软件的设置里查看「HTTP 代理端口 / 混合端口」(常见有 7890、7897、10809 等), 不要直接照抄示例端口;
- **代理失效自动回退**: 如果填了 `proxy` 但代理软件没有启动, 脚本启动时会检测并自动回退为直连(控制台会有提示), 不会因为代理问题直接卡死。

> 简单说: 能直连就用直连; 总是超时再挂代理, 并确认代理已开启、端口填写正确。

## 使用建议

- 提前在 B站会员购 完善实名信息, 并添加好对应观演人;
- 首次使用建议 `auto_pay` 填 `false`, 完整走一遍流程确认无误后再开启自动下单;
- 本脚本的主要场景是**售罄后的回流票捡漏**, 请保持脚本持续运行, 开演前常会有余票回落;
- 轮询间隔不建议低于 0.5 秒, 请求过于频繁容易触发风控;
- `cookies.pkl` 相当于账号钥匙, 请勿上传、分享, 也不要在公共电脑上使用。

## 常见问题

**Q: 提示登录失效 / 页面弹出登录框?**
A: 删除项目目录下的 `cookies.pkl`, 重新运行脚本扫码登录即可。

**Q: 提示 ChromeDriver 版本不匹配?**
A: 将 `config.json` 中的 `driver_path` 留空, 交由 Selenium 自动匹配; 或按「浏览器驱动说明」手动下载与本机 Chrome 大版本一致的驱动(放进项目文件夹并填相对路径)。

**Q: 直连超时较多?**
A: 参考「网络与代理」一节配置本地代理; 注意代理端口要在你本机的代理软件里确认, 配置后接口和浏览器都会走该代理, 代理未启动时脚本会自动回退直连。

**Q: 没有收到系统通知?**
A: 系统通知通过 macOS 的 `osascript` 实现, 仅 macOS 有效; 其他系统只会在控制台输出提示, 不影响抢票功能。

**Q: 自动下单成功了么?**
A: 以浏览器页面为准: 页面跳离确认订单页即表示订单已创建, 请尽快完成支付; 若仍停留在确认页, 请手动核对后处理。

**Q: 为什么配置文件叫 `config.json.example`? 直接改这个文件不行么?**
A: `.example` 后缀表示这是给所有人共用的**配置模板**: 请复制为 `config.json` 后再填写你自己的信息。`config.json` 已被 `.gitignore` 排除, 不会被误传到仓库; 而模板文件属于仓库内容, 直接改它的话, 下次拉取更新时你的修改可能被覆盖——所以「复制一份再改」是最稳妥的用法。

## 目录结构

```
BiliHelper/
├── main.py              # 主脚本
├── config.json.example  # 配置模板: 复制为 config.json 后修改, 请勿直接改本文件
├── requirements.txt     # Python 依赖
├── README.md
├── LICENSE
└── .gitignore
```

运行后会生成 `config.json`(你的个人配置) 与 `cookies.pkl`(登录状态), 二者均已被 `.gitignore` 排除, 不会被提交。

## 免责声明

- 本项目仅供个人学习、技术交流与亲友购票使用;
- 请遵守哔哩哔哩平台的相关协议与规则, 以及所在地区的法律法规;
- 请勿将本项目用于任何形式的商业代抢、囤票倒卖行为;
- 使用本项目产生的一切后果(包括但不限于账号风险、订单与资金问题)由使用者自行承担, 作者不承担任何责任。

## 致谢

- 思路与代码结构参考了社区开源项目 [damaihelper](https://github.com/Guyungy/damaihelper)
- 感谢所有开源贡献者

## 支持💕

如果你在本项目的帮助下成功抢到票，欢迎在以下平台支持我，这有助于开发出更优质的工具：
- [**Ko-fi**](https://ko-fi.com/jerryliiiiii) ☕️ Buy me a coffee
- [🇨🇳**爱发电**](https://afdian.com/a/JerryLiiiiii) 推荐中国大陆用户

## License

MIT License, 详见 [LICENSE](LICENSE)
