# Apple iPhone Duo 512GB 到店自取监控

免费、只读。监控 Seattle/Kirkland 和 Portland 的 **8 家官方 Apple Store × 2 色 × 仅 512GB**。不登录 Apple、不下单、不操作订单，不修改现有 ChatGPT 条件监控。

> 这是 Apple 官网未公开文档的自取接口监控。报警表示两轮新请求均返回可用，**不是已预留或已确认的预约时段**。必须打开 Apple 商品页，选对应门店，确认自取后自行决定是否购买。库存、接口、云端访问限制都可能变化。

## 快速配置

1. 使用 GitHub **公开仓库**和标准 `ubuntu-latest` 运行器。代码与门店列表公开；通知频道、邮箱与凭据只放 **Settings → Secrets and variables → Actions → Secrets**。不要提交 `.env`。
2. 手机安装 [ntfy App](https://ntfy.sh/)，订阅一个至少 20 字符的随机频道；在仓库新增 Secret **`NTFY_TOPIC`**，值就是频道名。默认服务器 `https://ntfy.sh`，无需账号。也可用 Telegram，见下表。
3. 打开 **Actions → Apple pickup monitor → Run workflow**，选择 **test**。确认手机收到带 `TEST` 的消息，再选择 **dry-run**，确认最新八店两色检查成功。
4. 在 **Settings → Secrets and variables → Actions → Variables** 新增 **`MONITOR_ENABLED` = `true`**，启用每 10 分钟检查（UTC 每小时第 7、17、27、37、47、57 分钟，避开整点）。选择 **run** 手动跑一次，确认状态分支已创建。
5. 检查 Actions 的第一次定时运行，确认绿色。`available: 0, unavailable: 16, unknown: 0` 才是完整的未见库存；`unknown`、红色运行或没有运行，都不能解释为无货。

**ntfy 隐私：**免费公共频道没有独占读取权限，知道频道名的人可能读写该频道。使用随机名称、保存在 Secrets，别把订阅链接贴到公开仓库；频道中只发送商品/门店信息。供应商或手机的推送接受成功不等于通知已在锁屏显示，首次请实际测试通知权限。

## 手机与邮件渠道

可同时启用多个渠道。成功渠道单独去重，失败渠道仅在库存再次实时确认可用时重试，避免重发过期库存。

| Secret | 用途 |
|---|---|
| `NTFY_TOPIC` | ntfy 随机频道名，至少20字符 |
| `NTFY_SERVER` | 可选，默认 `https://ntfy.sh` |
| `NTFY_TOKEN` | 可选，用于你的认证服务器 |
| `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID` | 可选，需成对填写。通过 [BotFather](https://t.me/BotFather) 建机器人，先给机器人发 `/start`，再取得 chat ID |
| `SMTP_HOST`, `SMTP_USER`, `SMTP_PASSWORD` | 邮件发信服务器、账号、应用专用密码 |
| `MAIL_FROM`, `MAIL_TO` | 发信地址、收信地址。不要公开提交实际地址 |
| `SMTP_PORT` | 可选，默认587；SSL通常465 |
| `SMTP_SECURITY` | 默认 `starttls`，也支持 `ssl`；禁用明文公网SMTP |

**Gmail 免费邮件示例：**`SMTP_HOST=smtp.gmail.com`、`SMTP_PORT=587`、`SMTP_SECURITY=starttls`，`SMTP_USER` 和 `MAIL_FROM` 填你的发件 Gmail 地址，`SMTP_PASSWORD` 填 Google **应用专用密码**，`MAIL_TO` 填收件地址。可发给自己。Google通常要求先开启两步验证，部分账号不能创建应用密码；参阅 [Google 官方说明](https://support.google.com/accounts/answer/185833)。**不要填 Google 登录密码，也不要把密码发到聊天。** 直接在 GitHub Secrets 页面填写，可随时在 Google 撤销应用密码。

邮件通过已有邮箱的 SMTP 服务发送，不用 ntfy 的付费邮件转发。邮箱服务自身限制与可用性以其规则为准。未配置邮件凭据时只有已配置的手机渠道工作，不能声称邮件已启用。GitHub Actions 自身失败邮件可另外在账号通知设置中启用，它不替代库存邮件。

## 监控范围与商品验证

2026-10-26 从 Apple 美国官网指定商品页的 JSON-LD `Product.name`、`color`、`offers[].sku` 和 `defaultOnloadPart`，以及 pickup 响应的完整标题核验：

| 512GB颜色 | Part number | Apple官方商品链接 |
|---|---|---|
| Star White 星白 | `MK1G4LL/A` | [购买页](https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-star-white-unlocked) |
| Night Sky 夜空 | `MK1H4LL/A` | [购买页](https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-night-sky-unlocked) |

只监控美国 `Connect on your own later` 对应型号，链接固定到已验证的容量/颜色选择。未证明所有运营商付款/激活方案均共享同样可下单资格，不将某一方案的库存信号作为其他方案保证。商品链接不会自动预选门店或预留库存，报警同时附官方门店页及门店ID。

| Seattle/Kirkland | Store ID | Portland | Store ID |
|---|---|---|---|
| Bellevue Square | R003 | Pioneer Place | R077 |
| University Village | R072 | Washington Square | R090 |
| Alderwood | R100 | Bridgeport Village | R134 |
| Southcenter | R106 | | |
| Tacoma Mall | R339 | | |

查询 ZIP 是 **98033、97204**。相邻门店返回数量可能变化；门店缺失记未知，绝不当无货。结果按确切门店ID与名称过滤，排除额外返回的门店。

## 防误报与去重

- 仅使用 `/shop/retail/pickup-message?pl=true&location=...&parts.0=...&parts.1=...`。旧 `/shop/fulfillment-messages` 本次实测541，不使用、不做备用。接口不是 Apple 承诺支持的公开API。
- 每个请求带随机参数、`Cache-Control: no-cache, no-store`。要求 HTTP Date 在120秒内、Age为0或缺省、无已知过期Warning/缓存命中。拒绝HTML、错误状态、重定向、异常结构。没有本地库存缓存回退。
- 同时验证 part key、`partNumber`、完整 `storePickupProductTitle`（Duo / 512GB / 对应颜色）、门店ID+名称、`pickupType=In-Store Pickup`、`pickupDisplay=available`、`storePickEligible=true`、`storeSelectionEnabled=true` 和自取时间原文。配送/送达字段完全不参与。
- 可用候选间隔至少2秒，再查询两个区域确认；消失、冲突或复核失败时不发到货提醒。两次新响应仍不能证明 Apple 后台绝无陈旧数据，也不能代替结账页确认。
- `Today/Tomorrow` 按 **America/Los_Angeles** 转成日历日期；其他格式保留Apple原文，明确标注日历日期未验证，不凭空猜日期。
- 同店同色同自取日期每渠道提醒一次。连续两轮**明确无货**才重置；未知会打断连续无货计数。首次运行可用会提醒，自取日期变化会再提醒。
- GitHub `monitor-state` 独立分支保存去重、退避和健康状态，不使用会被淘汰的 Actions cache。分支或内容损坏立即停止，不静默重置。删除状态分支会使下次可用重新提醒。不要手动删除。
- 429遵守 `Retry-After`；403/429/541至少暂停1小时，网络失败指数退避。遇到阻断不换代理、不密集重试。连续3次不完整检查后发送故障提醒，同渠道最多6小时一次。每次失败运行保持红色以便检查。
- 发送成功后再保存状态，属于 **at-least-once**：若供应商接受后进程崩溃或保存失败，可能重复提醒。SMTP仅能证明服务器接受，不能保证收件箱投递。持续无货不发噪音邮件。

## 免费托管的限制

[GitHub 官方计费规则](https://docs.github.com/en/billing/concepts/product-billing/github-actions)：公开仓库的标准GitHub托管运行器免费；不要启用大型付费运行器。私有仓库共享账号免费分钟额度，超额可能收费；要改成私有，先降低频率并将支出预算设为0。30分钟一次，一个31天月份有1488次，**仅当每次计费1分钟时**约1488分钟，测试、重跑、超时都会增加。

[GitHub 定时任务限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)：定时任务可能延迟甚至丢弃，最小间隔5分钟，公开仓库60天无活动可能停用。10分钟检查也可能错过一分钟以内的库存；本项目不保证“刚出现就通知”。不要为了保活制造无意义提交。定期查看Actions最后运行时间，原有ChatGPT每小时监控继续兜底。若Apple屏蔽GitHub数据中心IP，程序如实报未知；可在自己电脑定时运行同一项目，不能声称云监控仍正常。

默认 `MONITOR_ENABLED` 未设置前不会定时查询，手动test/dry-run仍可用。停止监控：将该变量改为 `false`；无需删除仓库或 Secrets。

## 本地运行与测试

Python 3.12+，Linux通常自带时区数据；Windows若报找不到时区，执行 `python -m pip install tzdata`。无其他第三方运行依赖。

```sh
python -m unittest discover -s tests -v
python verify_catalog.py
python monitor.py --dry-run
# 先通过系统环境变量配置通知渠道（不自动读取.env）
python monitor.py --test-notifications
python monitor.py
```

本地默认状态 `work/state.json`、报告 `work/latest.json`，dry-run不改变去重状态、不发送消息。实际监控请串行运行，避免两个本地进程同时写同一状态；云端通过workflow concurrency串行化。

## 开源工具评估与验证记录

- [bilune/apple-pickup-monitor](https://github.com/bilune/apple-pickup-monitor)：MIT，Python标准库，ntfy/Telegram，新pickup接口；适合作为接口发现和轻量本地监控参考。默认是NYC iPhone 18 Pro Max，不能直接用于本项目。本项目独立实现，未复制其源码。
- 本项目补充SMTP、按渠道持久化去重、严格商品/门店校验、响应新鲜度、二次确认及GitHub状态分支。详见 [验证记录](docs/verification.md)。开源项目对自身效果的描述不是本项目的实测保证。

源码采用 MIT，见 LICENSE。
