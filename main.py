#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金价格定时推送主调度脚本

在各机构开市时段，每半小时自动抓取黄金价格数据并推送到企业微信群。

各市场开市时间（北京时间）：
- 上海AU99.99: 日市 9:00-15:30, 夜市 20:00-次日2:30
- 银行账户黄金(纸黄金): 周一7:00至周六4:00（连续交易）
- 伦敦金(现货黄金): 周一7:00至周六4:00（几乎24小时）
- 周大福金店: 每日9:00-22:00

综合推送时段（取并集，周一至周五）：
- 日市: 09:00, 09:30, 10:00, ..., 15:30
- 夜市: 20:00, 20:30, 21:00, ..., 02:30
"""

import os
import sys
import time
import signal
import logging
from datetime import datetime, timedelta

# 添加当前目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from gold_price_fetcher import get_gold_price_message
from wecom_sender import send_text_message

# ==================== 配置 ====================

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

# 推送时段配置（24小时制）
# 日市时段: 9:00 - 15:30
# 夜市时段: 20:00 - 02:30（跨日）
DAY_SESSION_START = (9, 0)    # 日市开始 09:00
DAY_SESSION_END = (15, 30)    # 日市结束 15:30
NIGHT_SESSION_START = (20, 0)  # 夜市开始 20:00
NIGHT_SESSION_END = (2, 30)    # 夜市结束 02:30（次日）

# 每次发送间隔（秒）- 半小时 = 1800秒
SEND_INTERVAL = 1800

# ==================== 时间判断 ====================

def is_weekday(now=None):
    """判断是否为工作日（周一至周五）"""
    if now is None:
        now = datetime.now()
    return now.weekday() < 5  # 0=周一, 4=周五


def is_saturday(now=None):
    """判断是否为周六（覆盖周五夜市到周六凌晨）"""
    if now is None:
        now = datetime.now()
    return now.weekday() == 5  # 5=周六


def in_day_session(now=None):
    """
    判断当前时间是否在日市时段内 (9:00 - 15:30)
    周一至周五有效
    """
    if now is None:
        now = datetime.now()
    if not is_weekday(now):
        return False
    current_minutes = now.hour * 60 + now.minute
    start_minutes = DAY_SESSION_START[0] * 60 + DAY_SESSION_START[1]
    end_minutes = DAY_SESSION_END[0] * 60 + DAY_SESSION_END[1]
    return start_minutes <= current_minutes <= end_minutes


def in_night_session(now=None):
    """
    判断当前时间是否在夜市时段内 (20:00 - 次日02:30)
    - 周一至周五 20:00-23:59 有效
    - 周二至周六 00:00-02:30 有效（对应前一交易日的夜市）
    """
    if now is None:
        now = datetime.now()
    current_minutes = now.hour * 60 + now.minute
    start_minutes = NIGHT_SESSION_START[0] * 60 + NIGHT_SESSION_START[1]
    end_minutes = NIGHT_SESSION_END[0] * 60 + NIGHT_SESSION_END[1]

    # 20:00-23:59: 周一至周五
    if current_minutes >= start_minutes:
        if is_weekday(now):
            return True
    # 00:00-02:30: 周二至周六（前一交易日的夜市延续）
    if current_minutes <= end_minutes:
        if is_weekday(now) or is_saturday(now):
            return True

    return False


def is_market_open(now=None):
    """
    判断当前是否处于任一市场开市时段
    日市或夜市任一开市即返回True
    """
    return in_day_session(now) or in_night_session(now)


def next_send_time(now=None):
    """
    计算下一个整点或半点发送时间
    发送时间点: :00 和 :30
    """
    if now is None:
        now = datetime.now()

    minute = now.minute
    second = now.second

    if minute < 30:
        # 下一个发送点为当前小时的 :30
        next_time = now.replace(minute=30, second=0, microsecond=0)
    else:
        # 下一个发送点为下一小时的 :00
        next_time = (now.replace(minute=0, second=0, microsecond=0) + timedelta(hours=1))

    return next_time


def seconds_until_next_send(now=None):
    """计算距离下一个发送时间点的秒数"""
    if now is None:
        now = datetime.now()
    nxt = next_send_time(now)
    delta = nxt - now
    return max(int(delta.total_seconds()), 0)


# ==================== 主逻辑 ====================

def do_send():
    """执行一次数据抓取和推送"""
    logger.info("开始抓取黄金价格数据...")

    try:
        message = get_gold_price_message()
        if not message:
            logger.error("获取数据失败，跳过本次推送")
            return False

        logger.info(f"数据获取成功，开始推送消息...")
        result = send_text_message(message)

        if result and result.get("errcode") == 0:
            logger.info("推送成功！")
            return True
        else:
            logger.error(f"推送失败: {result}")
            return False

    except Exception as e:
        logger.error(f"推送过程异常: {e}", exc_info=True)
        return False


def run_daemon():
    """
    守护进程模式：持续运行，在开市时段每半小时自动推送

    发送时间点：每个整点的 :00 和 :30
    """
    logger.info("=" * 60)
    logger.info("黄金价格推送机器人启动")
    logger.info("=" * 60)
    logger.info(f"推送时段: 日市 {DAY_SESSION_START[0]:02d}:{DAY_SESSION_START[1]:02d}"
                f" - {DAY_SESSION_END[0]:02d}:{DAY_SESSION_END[1]:02d}"
                f" | 夜市 {NIGHT_SESSION_START[0]:02d}:{NIGHT_SESSION_START[1]:02d}"
                f" - {NIGHT_SESSION_END[0]:02d}:{NIGHT_SESSION_END[1]:02d}")
    logger.info(f"发送频率: 每30分钟 (:00 和 :30)")
    logger.info(f"企业微信Webhook已配置")
    logger.info("=" * 60)

    # 优雅退出处理
    running = [True]

    def signal_handler(signum, frame):
        logger.info(f"收到信号 {signum}，准备退出...")
        running[0] = False

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    last_sent_hour = -1
    last_sent_minute = -1

    while running[0]:
        now = datetime.now()

        # 检查是否到了发送时间点（:00 或 :30）
        is_send_minute = (now.minute == 0 or now.minute == 30)

        # 避免同一分钟内重复发送
        already_sent = (last_sent_hour == now.hour and last_sent_minute == now.minute)

        if is_send_minute and not already_sent:
            if is_market_open(now):
                logger.info(f"当前时间 {now.strftime('%Y-%m-%d %H:%M:%S')} 处于开市时段，执行推送...")
                do_send()
                last_sent_hour = now.hour
                last_sent_minute = now.minute
            else:
                logger.info(f"当前时间 {now.strftime('%Y-%m-%d %H:%M:%S')} 非开市时段，跳过推送")
                last_sent_hour = now.hour
                last_sent_minute = now.minute

        # 每秒检查一次
        time.sleep(1)

    logger.info("黄金价格推送机器人已停止")


def run_once(force=False):
    """
    单次执行模式：立即抓取并发送一次黄金价格

    Args:
        force: 是否强制发送（忽略开市时段判断）
    """
    now = datetime.now()
    if not force:
        if not is_market_open(now):
            logger.info(f"当前时间 {now.strftime('%Y-%m-%d %H:%M:%S')} 非开市时段，跳过推送")
            return False
        # 检查是否在 :00 或 :30 时间点（允许±2分钟的误差）
        minute = now.minute
        if minute not in (0, 1, 2, 28, 29, 30, 31, 32, 58, 59):
            logger.info(f"当前时间 {now.strftime('%H:%M')} 不在发送时间点(:00/:30)，跳过推送")
            return False

    logger.info("单次执行模式：立即推送一次黄金价格")
    success = do_send()
    return success


def run_test():
    """测试模式：只获取数据不发送"""
    logger.info("测试模式：只获取数据不发送")
    message = get_gold_price_message()
    if message:
        print("\n" + "=" * 60)
        print(message)
        print("=" * 60)
        logger.info("数据获取成功！")
        return True
    else:
        logger.error("数据获取失败！")
        return False


def print_schedule():
    """打印当前调度信息"""
    now = datetime.now()
    logger.info(f"当前时间: {now.strftime('%Y-%m-%d %H:%M:%S')} (星期{now.weekday()+1})")
    logger.info(f"日市时段: {DAY_SESSION_START[0]:02d}:{DAY_SESSION_START[1]:02d}"
                f" - {DAY_SESSION_END[0]:02d}:{DAY_SESSION_END[1]:02d}"
                f" | 当前在日市: {'是' if in_day_session(now) else '否'}")
    logger.info(f"夜市时段: {NIGHT_SESSION_START[0]:02d}:{NIGHT_SESSION_START[1]:02d}"
                f" - {NIGHT_SESSION_END[0]:02d}:{NIGHT_SESSION_END[1]:02d}"
                f" | 当前在夜市: {'是' if in_night_session(now) else '否'}")
    logger.info(f"市场开市: {'是' if is_market_open(now) else '否'}")

    nxt = next_send_time(now)
    wait_secs = seconds_until_next_send(now)
    logger.info(f"下次发送时间: {nxt.strftime('%Y-%m-%d %H:%M:%S')} (等待 {wait_secs} 秒)")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="黄金价格推送机器人")
    parser.add_argument("--daemon", action="store_true", help="守护进程模式，持续运行")
    parser.add_argument("--once", action="store_true", help="单次执行模式，立即推送一次（自动判断开市时段）")
    parser.add_argument("--force", action="store_true", help="强制推送（忽略开市时段判断，需配合 --once 使用）")
    parser.add_argument("--test", action="store_true", help="测试模式，只获取数据不发送")
    parser.add_argument("--schedule", action="store_true", help="显示当前调度信息")

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
        # 默认显示调度信息
        print_schedule()
        print("\n使用 --daemon 启动守护进程, --once 单次推送, --test 测试数据, --schedule 查看调度")
