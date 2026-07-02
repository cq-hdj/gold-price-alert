# gold-price-alert

每 30 分钟拉取 [FreeJK 上海黄金现货](https://freejk.com/api/47) 价格，推送到企业微信群机器人。

## 推送内容

- 国内现货价格（元/克）
- 较上次推送的涨跌
- 国际金价（USD/盎司）及折算参考
- 行情更新时间、检查时间

## Secret

| Name | 说明 |
|------|------|
| `WECOM_WEBHOOK` | 企业微信群机器人 Webhook |

## 手动测试

Actions → **Gold Price Alert** → **Run workflow**
