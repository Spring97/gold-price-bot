# 黄金价格推送机器人 - 部署指南

## 一、项目简介

自动抓取各类黄金价格行情数据，在各机构开市时段每半小时推送到企业微信群。

### 推送内容

| 品种 | 数据源 | 单位 |
|------|--------|------|
| 金店-周大福 | 金投网 API | 元/克 |
| 银行-美元账户黄金 | 工行纸黄金(美元) | 美元/盎司 |
| 银行-人民币账户黄金 | 工行纸黄金(人民币) | 元/克 |
| 伦敦金 | 现货黄金 XAU | 美元/盎司 |
| 上海-AU99.99 | 上海黄金交易所 | 元/克 |

### 推送时段

| 时段 | 时间 | 说明 |
|------|------|------|
| 日市 | 09:00 - 15:30 | 周一至周五 |
| 夜市 | 20:00 - 02:30 | 周一至周五（夜市延续到周六凌晨）|

- **频率**：每半小时（:00 和 :30）

---

## 二、文件清单

```
gold_price_bot/
├── main.py                  # 主调度脚本（核心）
├── gold_price_fetcher.py    # 数据抓取模块
├── wecom_sender.py          # 企业微信推送模块
├── cron_send.sh             # cron定时调用脚本
├── deploy.sh                # 一键部署脚本
├── start.sh                 # 快速启动脚本
├── requirements.txt         # Python依赖
├── gold_price_bot.service   # systemd服务文件（可选）
├── DEPLOY.md                # 本部署指南
├── README.md                # 项目说明
└── logs/                    # 日志目录（运行后自动创建）
```

---

## 三、部署方式

### 方式一：一键部署（推荐）

将整个 `gold_price_bot` 目录上传到服务器，然后执行：

```bash
# 赋予执行权限
chmod +x deploy.sh

# 执行一键部署（默认安装到 /opt/gold_price_bot）
sudo bash deploy.sh

# 或者指定安装目录
sudo bash deploy.sh /home/user/gold_bot
```

部署脚本会自动完成：
1. 检查 Python 环境
2. 安装 requests 依赖
3. 复制文件到部署目录
4. 测试数据获取
5. 配置 cron 定时任务

---

### 方式二：手动部署

#### 1. 上传文件

将 `gold_price_bot` 整个目录上传到服务器，例如放到 `/opt/gold_price_bot`。

#### 2. 安装 Python 依赖

```bash
# 确保有 Python 3.6+
python3 --version

# 安装 requests 库
pip3 install requests
# 或
sudo apt-get install python3-requests   # Ubuntu/Debian
sudo yum install python3-requests       # CentOS/RHEL
```

#### 3. 测试运行

```bash
cd /opt/gold_price_bot

# 测试数据获取（不发送消息）
python3 main.py --test

# 强制推送一次（验证企业微信机器人）
python3 main.py --once --force
```

#### 4. 配置 cron 定时任务

```bash
crontab -e
```

添加以下内容（注意修改路径）：

```
0,30 * * * * /opt/gold_price_bot/cron_send.sh
```

保存退出后，cron 会在每小时的 :00 和 :30 自动触发。脚本内置开市时段判断，非开市时段自动跳过。

---

### 方式三：systemd 守护进程（可选）

如果你更希望用 systemd 管理进程（自动重启、开机自启），可以：

```bash
# 1. 复制 service 文件
sudo cp /opt/gold_price_bot/gold_price_bot.service /etc/systemd/system/

# 2. 编辑文件，确认路径正确
sudo vim /etc/systemd/system/gold_price_bot.service
# 确认 WorkingDirectory 和 ExecStart 中的路径

# 3. 启动服务
sudo systemctl daemon-reload
sudo systemctl enable gold_price_bot
sudo systemctl start gold_price_bot

# 4. 查看状态
sudo systemctl status gold_price_bot
```

> **注意**：如果使用 systemd 守护进程模式，可以不需要 cron。两种方式选其一即可，避免重复推送。

---

## 四、常用命令

```bash
# 查看当前调度状态
python3 /opt/gold_price_bot/main.py --schedule

# 立即强制推送一次（忽略开市时段）
python3 /opt/gold_price_bot/main.py --once --force

# 在开市时段推送（自动判断 :00/:30 时间点）
python3 /opt/gold_price_bot/main.py --once

# 测试数据获取（不发送消息）
python3 /opt/gold_price_bot/main.py --test

# 启动守护进程
python3 /opt/gold_price_bot/main.py --daemon
```

---

## 五、日志查看

```bash
# 主日志
tail -f /opt/gold_price_bot/logs/gold_bot.log

# cron 执行日志
tail -f /opt/gold_price_bot/logs/cron.log

# systemd 日志（如使用 systemd）
journalctl -u gold_price_bot -f
```

---

## 六、配置修改

### 修改企业微信 Webhook 地址

编辑 `wecom_sender.py`，修改第 12 行：

```python
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=你的KEY"
```

### 修改推送时段

编辑 `main.py`，修改以下变量：

```python
DAY_SESSION_START = (9, 0)     # 日市开始
DAY_SESSION_END = (15, 30)     # 日市结束
NIGHT_SESSION_START = (20, 0)  # 夜市开始
NIGHT_SESSION_END = (2, 30)    # 夜市结束
```

### 修改发送频率

当前为每半小时（:00 和 :30）。如需改为每小时一次，修改 cron：

```bash
crontab -e
# 改为: 0 * * * * /opt/gold_price_bot/cron_send.sh
```

---

## 七、消息格式示例

```
金店-周大福
💰黄金价:(￥): 1308.00
金条价: 1148.00
单位: 元/克
更新时间: 2026-08-10 10:11:18
 
银行-美元账户黄金
🔥中间价($):  4326.6750
买入价: 4325.0550
卖出价: 4328.2950
最高价: 4347.2450
最低价: 4313.1550
更新时间: 2026-08-10 11:30:51
 
银行-人民币账户黄金
🏆中间价(￥): 938.53
买入价: 938.28
卖出价: 938.78
最高价: 942.73
最低价: 935.36
更新时间: 2026-08-10 11:30:51
 
伦敦金
👍最新价:($): 4326.52
开盘价: 4340.59
最高价: 4348.99
最低价: 4311.49
昨收盘价: 4341.83
更新时间: 2026-08-10 11:30:57
 
上海-AU99.99
🚀当前价:(￥): 938.90
开盘价: 938.00
最高价: 948.00
最低价: 934.00
涨跌幅: 0.91
昨日收盘价: 930.47
总成交量: 193784.00
更新时间: 2026-08-10 11:30:13
```

---

## 八、常见问题

### Q: 消息没有发送？

1. 检查网络：`python3 main.py --test`
2. 检查 cron 是否运行：`ps aux | grep cron`
3. 检查日志：`cat logs/cron.log`
4. 手动测试：`python3 main.py --once --force`

### Q: 数据显示 "--"？

说明 API 返回的数据中该字段为空，可能该品种当前未开市（如周大福在非营业时间不更新价格）。

### Q: 如何停止推送？

```bash
# 停止 cron
crontab -l | grep -v gold_price_bot | crontab -

# 停止 systemd（如使用）
sudo systemctl stop gold_price_bot
```

### Q: 数据来源是什么？

所有数据来自金投网（cngold.org）的行情 API：

```
https://api.jijinhao.com/quoteCenter/realTime.htm
```

请求时需要带 `Referer: https://quote.cngold.org/` 头。
