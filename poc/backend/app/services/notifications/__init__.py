"""Sprint 15.4 — 通知触发器分发服务 (PRD §L412).

调用入口：app.services.notifications.dispatch(...)
  - 检查 TenantSettings 对应事件开关 (notify_quota_warning / ...)
  - 按 TenantSettings.notify_channels 路由到各渠道：
      system  → 写 notification 表
      sms     → 阿里云 SMS HTTP（dev 模式 log）
      wechat  → 企微机器人 webhook
      dingtalk→ 钉钉机器人 webhook
"""
from .dispatcher import dispatch, EventType  # noqa: F401
