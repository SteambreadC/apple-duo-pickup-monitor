# 本次部署验收

日期：2026-10-26，America/Los_Angeles。

- [公开仓库](https://github.com/SteambreadC/apple-duo-pickup-monitor) 已创建并发布源码；运行器为标准Ubuntu。
- `NTFY_TOPIC` 已保存为仓库Secret，频道不在代码中；`MONITOR_ENABLED=true` 已保存为仓库Variable。定时规则为每10分钟，UTC每小时7/17/27/37/47/57分。GitHub可能延迟触发。
- [29项云端测试](https://github.com/SteambreadC/apple-duo-pickup-monitor/actions/runs/40441026865) 全部通过，含本机HTTP/SMTP协议测试（在云端运行器内的回环服务）。
- [首次云端实时dry-run](https://github.com/SteambreadC/apple-duo-pickup-monitor/actions/runs/40440694752)：19:50，available 0 / unavailable 16 / unknown 0。
- [完整监控+状态持久化](https://github.com/SteambreadC/apple-duo-pickup-monitor/actions/runs/40441237096)：19:55:42，available 0 / unavailable 16 / unknown 0；`monitor-state`分支创建成功，16组状态与最后成功时间已保存。
- 本地真实ntfy服务已接受明确标为TEST的消息。手机是否显示，需订阅频道并由用户确认。
- 独立代码审查发现并修复跨午夜重复通知和通知超时导致状态来不及保存的问题；修复后复查无剩余高/中优先级问题。
- **邮件仍待配置：**已提供SMTP适配器及测试，但实际发信凭据需账号持有人直接填入GitHub Secrets。尚未执行真实邮箱投递，不宣称邮件报警已开启。Telegram是可选备用渠道，代码与本地协议测试已具备，未配置真实机器人。

未购买任何产品，未访问或修改Apple账号/订单，未修改原有ChatGPT监控。上面的库存是验收时点的历史记录；当前库存必须由新请求确认。
