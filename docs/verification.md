# 验证记录

记录日期：2026-10-26（America/Los_Angeles）。这是历史验证记录，不能用作当前库存。

## 已实测

- Apple 美国官网两色512GB商品页 HTTP 200。JSON-LD：Star White `MK1G4LL/A+unlocked`，Night Sky `MK1H4LL/A+unlocked`；默认part与pickup标题一致。
- `/shop/retail/pickup-message` HTTP 200，无账号Cookie，支持两个parts合并。ZIP 98033及97204均返回目标门店，Store ID对应见README。响应包含pickup专用字段，未读取配送库存。
- 旧 `/shop/fulfillment-messages` 实测HTTP 541，不作为回退路径。
- 19:31:01 PDT 的首次Seattle查询、19:31:17的Portland查询中，Pioneer Place R077 Night Sky 512GB返回 `available`、`storePickEligible=true`、`storeSelectionEnabled=true`、`Available Tomorrow`；19:32:21新的随机参数查询已返回 `unavailable`。用户自己的Apple页面也未显示可取。不能证明真实库存持续了多久、有人买走，或能进入结账预约；作为接口短暂信号处理，不宣称成功预约。
- 19:41:17 PDT 使用交付项目 `monitor.py --dry-run` 重新查询：**available 0 / unavailable 16 / unknown 0**。无通知、无订单操作。
- 本地自动测试含严格身份匹配、缓存新鲜度、配送字段隔离、两次确认、未知状态、按渠道去重及重试、429/541退避、GitHub状态恢复。通知适配器对本机HTTP服务与SMTP服务完成真实协议测试；Telegram `ok=false`不记成功。

## 必须分开理解的状态

- 自动测试通过 ≠ Apple接口今后持续可用。
- Apple接口响应 ≠ 结账页能预约，更不是已预留。
- 本机HTTP/SMTP协议测试 ≠ 真实手机/邮箱收到。
- 发布代码 ≠ 定时任务已启用。`MONITOR_ENABLED=true`后才定时运行。
- 手机通知需在实际ntfy服务接受后，再由用户核对通知权限与收件；邮件需SMTP凭据后才能进行真实发送。
- GitHub托管runner是否被Apple限制，须由首次云端dry-run验证；本机成功不能替代。

## 参考资料（当前核验）

- Apple商品页：[星白](https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-star-white-unlocked)、[夜空](https://www.apple.com/shop/buy-iphone/iphone-duo/7.6-inch-display-512gb-night-sky-unlocked)。只将这些页面用于商品身份验证，搜索索引不用作实时库存来源。
- [bilune/apple-pickup-monitor](https://github.com/bilune/apple-pickup-monitor) 与其 `monitor.py`：确认MIT声明、新pickup接口与ntfy/Telegram做法；本项目独立实现。其NYC/Pro Max配置不适用于本需求，其库存持续时间描述也不是本地实测。
- [GitHub Actions计费](https://docs.github.com/en/billing/concepts/product-billing/github-actions)、[schedule限制](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows#schedule)。
- [ntfy发送](https://docs.ntfy.sh/publish/)、[Telegram sendMessage](https://core.telegram.org/bots/api#sendmessage)、[Google邮件应用密码说明](https://support.google.com/accounts/answer/185833)。

完整公开源码不包含真实频道名、收件邮箱、通知令牌或邮箱凭据。原始商品页和响应仅作为本地研究材料，程序不会重放它们作为当前库存。
