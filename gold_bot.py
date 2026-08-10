#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金价格推送机器人 - 单文件版
================================
各机构开市时段每半小时自动推送黄金价格到企业微信群

部署方法：
  1. 将此文件保存到服务器，如 /opt/gold_price_bot.py
  2. 安装依赖: pip3 install requests
  3. 测试: python3 /opt/gold_price_bot.py --test
  4. 推送: python3 /opt/gold_price_bot.py --once --force
  5. 设置cron: crontab -e
     添加: 0,30 * * * * python3 /opt/gold_price_bot.py --once

推送时段（北京时间）:
  日市: 周一至周五 09:00 - 15:30
  夜市: 周一至周五 20:00 - 次日 02:30
  频率: 每半小时 (:00 和 :30)
"""

import os
import re
import sys
import json
import time
import signal
import logging
import requests
from datetime import datetime, timedelta

# ==================== 配置 ====================

# 企业微信机器人Webhook地址
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84969200-e386-4102-af8a-42e274ca5cb7"

# 行情API配置
API_BASE = "https://api.jijinhao.com/quoteCenter/realTime.htm"
REFERER = "https://quote.cngold.org/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 商品代码
CODES = {
    "chowtaifook_gold": "JO_42660",   # 周大福黄金价格 (元/克)
    "chowtaifook_bar": "JO_56037",     # 周大福金条金价(内地) (元/克)
    "bank_usd_gold": "JO_42757",       # 工行纸黄金(美元) = 美元账户黄金
    "bank_cny_gold": "JO_42760",       # 工行纸黄金(人民币) = 人民币账户黄金
    "london_gold": "JO_92233",         # 现货黄金 = 伦敦金
    "shanghai_9999": "JO_71",          # 黄金9999 = AU99.99
}

# 推送时段
DAY_SESSION_START = (9, 0)
DAY_SESSION_END = (15, 30)
NIGHT_SESSION_START = (20, 0)
NIGHT_SESSION_END = (2, 30)

# 日志配置
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "logs")
os.makedirs(LOG_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(os.path.join(LOG_DIR, "gold_bot.log"), encoding="utf-8"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


# ==================== 数据抓取 ====================

def fetch_realtime_data():
    """从API获取所有黄金品种的实时行情数据"""
    codes_str = ",".join(CODES.values())
    headers = {"Referer": REFERER, "User-Agent": UA}
    params = {"codes": codes_str}

    try:
        resp = requests.get(API_BASE, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()
        text = re.sub(r'^var\s+quote_json\s*=\s*', '', text)
        text = text.rstrip(';').strip()
        data = json.loads(text)
        if not data.get("flag", False):
            logger.error(f"API返回flag=false: {data}")
            return None
        return data
    except Exception as e:
        logger.error(f"请求失败: {e}")
        return None


def _fmt(val, digits=2):
    if val is None or val == 0:
        return "--"
    return f"{val:.{digits}f}"


def _fmt_time(timestamp_ms):
    if not timestamp_ms:
        return "--"
    return datetime.fromtimestamp(timestamp_ms / 1000).strftime("%Y-%m-%d %H:%M:%S")


def parse_all_prices(data):
    """解析API数据，返回格式化消息文本"""
    if not data:
        return None

    parts = []

    # 1. 金店-周大福
    ctf_gold = data.get(CODES["chowtaifook_gold"], {})
    ctf_bar = data.get(CODES["chowtaifook_bar"], {})
    parts.append(
        f"金店-周大福\n"
        f"💰黄金价:(￥): {_fmt(ctf_gold.get('q63'))}\n"
        f"金条价: {_fmt(ctf_bar.get('q63'))}\n"
        f"单位: 元/克\n"
        f"更新时间: {_fmt_time(ctf_gold.get('time'))}"
    )

    # 2. 银行-美元账户黄金
    usd = data.get(CODES["bank_usd_gold"], {})
    parts.append(
        f"银行-美元账户黄金\n"
        f"🔥中间价($):  {_fmt(usd.get('q69'), 4)}\n"
        f"买入价: {_fmt(usd.get('q74'), 4)}\n"
        f"卖出价: {_fmt(usd.get('q73'), 4)}\n"
        f"最高价: {_fmt(usd.get('q71'), 4)}\n"
        f"最低价: {_fmt(usd.get('q72'), 4)}\n"
        f"更新时间: {_fmt_time(usd.get('time'))}"
    )

    # 3. 银行-人民币账户黄金
    cny = data.get(CODES["bank_cny_gold"], {})
    parts.append(
        f"银行-人民币账户黄金\n"
        f"🏆中间价(￥): {_fmt(cny.get('q69'))}\n"
        f"买入价: {_fmt(cny.get('q74'))}\n"
        f"卖出价: {_fmt(cny.get('q73'))}\n"
        f"最高价: {_fmt(cny.get('q71'))}\n"
        f"最低价: {_fmt(cny.get('q72'))}\n"
        f"更新时间: {_fmt_time(cny.get('time'))}"
    )

    # 4. 伦敦金
    ld = data.get(CODES["london_gold"], {})
    parts.append(
        f"伦敦金\n"
        f"👍最新价:($): {_fmt(ld.get('q63'))}\n"
        f"开盘价: {_fmt(ld.get('q1'))}\n"
        f"最高价: {_fmt(ld.get('q3'))}\n"
        f"最低价: {_fmt(ld.get('q4'))}\n"
        f"昨收盘价: {_fmt(ld.get('q2'))}\n"
        f"更新时间: {_fmt_time(ld.get('time'))}"
    )

    # 5. 上海-AU99.99
    sh = data.get(CODES["shanghai_9999"], {})
    chg = sh.get("q80")
    parts.append(
        f"上海-AU99.99\n"
        f"🚀当前价:(￥): {_fmt(sh.get('q63'))}\n"
        f"开盘价: {_fmt(sh.get('q1'))}\n"
        f"最高价: {_fmt(sh.get('q3'))}\n"
        f"最低价: {_fmt(sh.get('q4'))}\n"
        f"涨跌幅: {f'{chg:.2f}' if chg else '--'}\n"
        f"昨日收盘价: {_fmt(sh.get('q2'))}\n"
        f"总成交量: {_fmt(sh.get('q60'))}\n"
        f"更新时间: {_fmt_time(sh.get('time'))}"
    )

    return "\n \n".join(parts)


def get_gold_price_message():
    """获取黄金价格并返回格式化消息"""
    data = fetch_realtime_data()
    if not data:
        return None
    return parse_all_prices(data)


# ==================== 企业微信推送 ====================

def send_text_message(content):
    """发送text消息到企业微信群"""
    payload = {"msgtype": "text", "text": {"content": content}}
    try:
        resp = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=10
        )
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
    if now is None:
        now = datetime.now()
    return now.weekday() < 5

def is_saturday(now=None):
    if now is None:
        now = datetime.now()
    return now.weekday() == 5

def in_day_session(now=None):
    if now is None:
        now = datetime.now()
    if not is_weekday(now):
        return False
    cur = now.hour * 60 + now.minute
    return DAY_SESSION_START[0]*60+DAY_SESSION_START[1] <= cur <= DAY_SESSION_END[0]*60+DAY_SESSION_END[1]

def in_night_session(now=None):
    if now is None:
        now = datetime.now()
    cur = now.hour * 60 + now.minute
    start = NIGHT_SESSION_START[0]*60+NIGHT_SESSION_START[1]
    end = NIGHT_SESSION_END[0]*60+NIGHT_SESSION_END[1]
    if cur >= start and is_weekday(now):
        return True
    if cur <= end and (is_weekday(now) or is_saturday(now)):
        return True
    return False

def is_market_open(now=None):
    return in_day_session(now) or in_night_session(now)


# ==================== 主逻辑 ====================

def do_send():
    """执行一次数据抓取和推送"""
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
    """守护进程模式"""
    logger.info("=" * 60)
    logger.info("黄金价格推送机器人启动")
    logger.info(f"推送时段: 日市 09:00-15:30 | 夜市 20:00-02:30")
    logger.info(f"发送频率: 每30分钟 (:00 和 :30)")
    logger.info("=" * 60)

    running = [True]
    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备退出...")
        running[0] = False
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

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
    """单次推送"""
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
    """测试模式"""
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
    parser.add_argument("--once", action="store_true", help="单次推送（自动判断开市时段）")
    parser.add_argument("--force", action="store_true", help="强制推送（配合 --once 使用）")
    parser.add_argument("--test", action="store_true", help="测试数据获取（不发送）")
    parser.add_argument("--schedule", action="store_true", help="查看调度信息")
    args = parser.parse_args()

    if args.once:
        run_once(force=args.force)
    elif args.test:
        run_test()
    elif args.schedule:
        print_schedule()
    elif args.daemon:
        run_daemon()
    else:
        print_schedule()
        print("\n用法: --daemon 守护进程 | --once --force 立即推送 | --test 测试 | --schedule 调度信息")
