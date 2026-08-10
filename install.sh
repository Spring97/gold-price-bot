#!/bin/bash
# ============================================================
#  黄金价格推送机器人 - 服务器一键安装脚本
#  在服务器上执行: bash install_gold_bot.sh
# ============================================================

set -e
INSTALL_DIR="${1:-/opt/gold_price_bot}"

echo "============================================"
echo "  黄金价格推送机器人 - 一键安装"
echo "  安装目录: $INSTALL_DIR"
echo "============================================"

# 创建目录
mkdir -p "$INSTALL_DIR/logs"
cd "$INSTALL_DIR"

# 安装依赖
echo "[1/3] 安装Python依赖..."
pip3 install requests 2>/dev/null || pip install requests 2>/dev/null || {
    echo "  尝试使用系统包安装..."
    apt-get install -y python3-requests 2>/dev/null || yum install -y python3-requests 2>/dev/null || true
}
echo "  ✅ 依赖安装完成"

# 创建主程序文件
echo "[2/3] 创建程序文件..."
cat > "$INSTALL_DIR/gold_bot.py" << 'PYEOF'
#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金价格推送机器人 - 单文件版
各机构开市时段每半小时自动推送黄金价格到企业微信群

用法:
  python3 gold_bot.py --test           # 测试数据获取
  python3 gold_bot.py --once --force   # 立即推送一次
  python3 gold_bot.py --daemon         # 守护进程模式
  python3 gold_bot.py --schedule       # 查看调度信息

cron定时: 0,30 * * * * python3 /opt/gold_price_bot/gold_bot.py --once
"""

import os, re, sys, json, time, signal, logging, requests
from datetime import datetime, timedelta

# ==================== 配置 ====================
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84969200-e386-4102-af8a-42e274ca5cb7"
API_BASE = "https://api.jijinhao.com/quoteCenter/realTime.htm"
REFERER = "https://quote.cngold.org/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

CODES = {
    "chowtaifook_gold": "JO_42660",
    "chowtaifook_bar": "JO_56037",
    "bank_usd_gold": "JO_42757",
    "bank_cny_gold": "JO_42760",
    "london_gold": "JO_92233",
    "shanghai_9999": "JO_71",
}

DAY_SESSION_START = (9, 0)
DAY_SESSION_END = (15, 30)
NIGHT_SESSION_START = (20, 0)
NIGHT_SESSION_END = (2, 30)

LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.FileHandler(os.path.join(LOG_DIR, "gold_bot.log"), encoding="utf-8"), logging.StreamHandler()])
logger = logging.getLogger(__name__)

# ==================== 数据抓取 ====================
def fetch_realtime_data():
    codes_str = ",".join(CODES.values())
    try:
        resp = requests.get(API_BASE, headers={"Referer": REFERER, "User-Agent": UA},
                            params={"codes": codes_str}, timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()
        text = re.sub(r'^var\s+quote_json\s*=\s*', '', text).rstrip(';').strip()
        data = json.loads(text)
        if not data.get("flag", False):
            logger.error(f"API返回flag=false: {data}")
            return None
        return data
    except Exception as e:
        logger.error(f"请求失败: {e}")
        return None

def _fmt(val, digits=2):
    if val is None or val == 0: return "--"
    return f"{val:.{digits}f}"

def _fmt_time(ts):
    if not ts: return "--"
    return datetime.fromtimestamp(ts / 1000).strftime("%Y-%m-%d %H:%M:%S")

def parse_all_prices(data):
    if not data: return None
    parts = []
    # 1. 周大福
    cg = data.get(CODES["chowtaifook_gold"], {})
    cb = data.get(CODES["chowtaifook_bar"], {})
    parts.append(f"金店-周大福\n💰黄金价:(￥): {_fmt(cg.get('q63'))}\n金条价: {_fmt(cb.get('q63'))}\n单位: 元/克\n更新时间: {_fmt_time(cg.get('time'))}")
    # 2. 美元账户黄金
    usd = data.get(CODES["bank_usd_gold"], {})
    parts.append(f"银行-美元账户黄金\n🔥中间价($):  {_fmt(usd.get('q69'), 4)}\n买入价: {_fmt(usd.get('q74'), 4)}\n卖出价: {_fmt(usd.get('q73'), 4)}\n最高价: {_fmt(usd.get('q71'), 4)}\n最低价: {_fmt(usd.get('q72'), 4)}\n更新时间: {_fmt_time(usd.get('time'))}")
    # 3. 人民币账户黄金
    cny = data.get(CODES["bank_cny_gold"], {})
    parts.append(f"银行-人民币账户黄金\n🏆中间价(￥): {_fmt(cny.get('q69'))}\n买入价: {_fmt(cny.get('q74'))}\n卖出价: {_fmt(cny.get('q73'))}\n最高价: {_fmt(cny.get('q71'))}\n最低价: {_fmt(cny.get('q72'))}\n更新时间: {_fmt_time(cny.get('time'))}")
    # 4. 伦敦金
    ld = data.get(CODES["london_gold"], {})
    parts.append(f"伦敦金\n👍最新价:($): {_fmt(ld.get('q63'))}\n开盘价: {_fmt(ld.get('q1'))}\n最高价: {_fmt(ld.get('q3'))}\n最低价: {_fmt(ld.get('q4'))}\n昨收盘价: {_fmt(ld.get('q2'))}\n更新时间: {_fmt_time(ld.get('time'))}")
    # 5. 上海AU99.99
    sh = data.get(CODES["shanghai_9999"], {})
    chg = sh.get("q80")
    parts.append(f"上海-AU99.99\n🚀当前价:(￥): {_fmt(sh.get('q63'))}\n开盘价: {_fmt(sh.get('q1'))}\n最高价: {_fmt(sh.get('q3'))}\n最低价: {_fmt(sh.get('q4'))}\n涨跌幅: {f'{chg:.2f}' if chg else '--'}\n昨日收盘价: {_fmt(sh.get('q2'))}\n总成交量: {_fmt(sh.get('q60'))}\n更新时间: {_fmt_time(sh.get('time'))}")
    return "\n \n".join(parts)

def get_gold_price_message():
    data = fetch_realtime_data()
    if not data: return None
    return parse_all_prices(data)

# ==================== 企业微信推送 ====================
def send_text_message(content):
    payload = {"msgtype": "text", "text": {"content": content}}
    try:
        resp = requests.post(WEBHOOK_URL, headers={"Content-Type": "application/json"},
                             data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), timeout=10)
        result = resp.json()
        if result.get("errcode") == 0:
            logger.info("消息发送成功")
            return True
        else:
            logger.error(f"消息发送失败: {result}")
            return False
    except Exception as e:
        logger.error(f"发送异常: {e}")
        return False

# ==================== 时间判断 ====================
def is_weekday(now=None):
    return (now or datetime.now()).weekday() < 5

def is_saturday(now=None):
    return (now or datetime.now()).weekday() == 5

def in_day_session(now=None):
    now = now or datetime.now()
    if not is_weekday(now): return False
    cur = now.hour * 60 + now.minute
    return DAY_SESSION_START[0]*60+DAY_SESSION_START[1] <= cur <= DAY_SESSION_END[0]*60+DAY_SESSION_END[1]

def in_night_session(now=None):
    now = now or datetime.now()
    cur = now.hour * 60 + now.minute
    start = NIGHT_SESSION_START[0]*60+NIGHT_SESSION_START[1]
    end = NIGHT_SESSION_END[0]*60+NIGHT_SESSION_END[1]
    if cur >= start and is_weekday(now): return True
    if cur <= end and (is_weekday(now) or is_saturday(now)): return True
    return False

def is_market_open(now=None):
    return in_day_session(now) or in_night_session(now)

# ==================== 主逻辑 ====================
def do_send():
    logger.info("开始抓取黄金价格数据...")
    try:
        message = get_gold_price_message()
        if not message:
            logger.error("获取数据失败，跳过本次推送")
            return False
        logger.info("数据获取成功，开始推送...")
        return send_text_message(message)
    except Exception as e:
        logger.error(f"推送异常: {e}", exc_info=True)
        return False

def run_daemon():
    logger.info("=" * 60)
    logger.info("黄金价格推送机器人启动")
    logger.info("推送时段: 日市 09:00-15:30 | 夜市 20:00-02:30 | 频率: 每30分钟")
    logger.info("=" * 60)
    running = [True]
    def handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备退出...")
        running[0] = False
    signal.signal(signal.SIGINT, handler)
    signal.signal(signal.SIGTERM, handler)
    last_h, last_m = -1, -1
    while running[0]:
        now = datetime.now()
        if (now.minute == 0 or now.minute == 30) and not (last_h == now.hour and last_m == now.minute):
            if is_market_open(now):
                logger.info(f"{now.strftime('%H:%M:%S')} 开市时段，执行推送...")
                do_send()
            else:
                logger.info(f"{now.strftime('%H:%M:%S')} 非开市时段，跳过")
            last_h, last_m = now.hour, now.minute
        time.sleep(1)
    logger.info("黄金价格推送机器人已停止")

def run_once(force=False):
    now = datetime.now()
    if not force:
        if not is_market_open(now):
            logger.info(f"{now.strftime('%Y-%m-%d %H:%M:%S')} 非开市时段，跳过推送")
            return False
        if now.minute not in (0, 1, 2, 28, 29, 30, 31, 32, 58, 59):
            logger.info(f"{now.strftime('%H:%M')} 不在发送时间点(:00/:30)，跳过")
            return False
    logger.info("单次推送模式")
    return do_send()

def run_test():
    logger.info("测试模式：只获取数据不发送")
    msg = get_gold_price_message()
    if msg:
        print("\n" + "=" * 60)
        print(msg)
        print("=" * 60)
        return True
    else:
        logger.error("数据获取失败")
        return False

def print_schedule():
    now = datetime.now()
    logger.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (星期{now.weekday()+1})")
    logger.info(f"日市 09:00-15:30 | 当前: {'是' if in_day_session(now) else '否'}")
    logger.info(f"夜市 20:00-02:30 | 当前: {'是' if in_night_session(now) else '否'}")
    logger.info(f"市场开市: {'是' if is_market_open(now) else '否'}")

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="黄金价格推送机器人")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式")
    parser.add_argument("--once", action="store_true", help="单次推送")
    parser.add_argument("--force", action="store_true", help="强制推送")
    parser.add_argument("--test", action="store_true", help="测试数据获取")
    parser.add_argument("--schedule", action="store_true", help="查看调度信息")
    args = parser.parse_args()
    if args.once: run_once(force=args.force)
    elif args.test: run_test()
    elif args.schedule: print_schedule()
    elif args.daemon: run_daemon()
    else:
        print_schedule()
        print("\n用法: --daemon | --once --force | --test | --schedule")
PYEOF
chmod +x "$INSTALL_DIR/gold_bot.py"
echo "  ✅ gold_bot.py 创建完成"

# 创建cron脚本
cat > "$INSTALL_DIR/cron_send.sh" << 'SHEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="/tmp/gold_price_bot_cron.lock"
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    [ "$LOCK_AGE" -lt 120 ] && exit 0
fi
touch "$LOCK_FILE"
cd "$SCRIPT_DIR"
python3 main.py --once >> "$SCRIPT_DIR/logs/cron.log" 2>&1
rm -f "$LOCK_FILE"
SHEOF
# 修正：cron脚本里应该调用 gold_bot.py
cat > "$INSTALL_DIR/cron_send.sh" << 'SHEOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOCK_FILE="/tmp/gold_price_bot_cron.lock"
if [ -f "$LOCK_FILE" ]; then
    LOCK_AGE=$(( $(date +%s) - $(stat -c %Y "$LOCK_FILE") ))
    [ "$LOCK_AGE" -lt 120 ] && exit 0
fi
touch "$LOCK_FILE"
cd "$SCRIPT_DIR"
python3 gold_bot.py --once >> "$SCRIPT_DIR/logs/cron.log" 2>&1
rm -f "$LOCK_FILE"
SHEOF
chmod +x "$INSTALL_DIR/cron_send.sh"
echo "  ✅ cron_send.sh 创建完成"

# 测试
echo "[3/3] 测试数据获取..."
python3 "$INSTALL_DIR/gold_bot.py" --test

echo ""
echo "============================================"
echo "  ✅ 安装完成！"
echo "============================================"
echo ""
echo "推送时段（北京时间）:"
echo "  日市: 周一至周五 09:00-15:30"
echo "  夜市: 周一至周五 20:00-02:30"
echo "  频率: 每半小时 (:00 和 :30)"
echo ""
echo "常用命令:"
echo "  立即推送: python3 $INSTALL_DIR/gold_bot.py --once --force"
echo "  测试数据: python3 $INSTALL_DIR/gold_bot.py --test"
echo "  查看调度: python3 $INSTALL_DIR/gold_bot.py --schedule"
echo "  守护进程: python3 $INSTALL_DIR/gold_bot.py --daemon"
echo ""
echo "设置cron定时任务（执行以下命令）:"
echo "  (crontab -l 2>/dev/null | grep -v gold_price_bot; echo '0,30 * * * * $INSTALL_DIR/cron_send.sh') | crontab -"
echo "============================================"
