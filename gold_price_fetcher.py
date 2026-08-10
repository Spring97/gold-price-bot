#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
黄金价格数据抓取模块
从金投网(cngold.org)的API接口获取各类黄金价格实时行情数据
"""

import re
import json
import time
import requests
from datetime import datetime

# API配置
API_BASE = "https://api.jijinhao.com/quoteCenter/realTime.htm"
REFERER = "https://quote.cngold.org/"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

# 商品代码映射
CODES = {
    # 周大福
    "chowtaifook_gold": "JO_42660",       # 周大福黄金价格 (元/克)
    "chowtaifook_bar": "JO_56037",         # 周大福金条金价(内地) (元/克)
    # 银行账户黄金（纸黄金）
    "bank_usd_gold": "JO_42757",           # 工行纸黄金(美元) = 美元账户黄金 (美元/盎司)
    "bank_cny_gold": "JO_42760",           # 工行纸黄金(人民币) = 人民币账户黄金 (元/克)
    # 伦敦金
    "london_gold": "JO_92233",             # 现货黄金 = 伦敦金 (美元/盎司)
    # 上海黄金交易所
    "shanghai_9999": "JO_71",              # 黄金9999 = AU99.99 (元/克)
}


def fetch_realtime_data():
    """
    从API获取所有黄金品种的实时行情数据
    返回解析后的字典
    """
    codes_str = ",".join(CODES.values())
    headers = {
        "Referer": REFERER,
        "User-Agent": UA,
    }
    params = {"codes": codes_str}

    try:
        resp = requests.get(API_BASE, headers=headers, params=params, timeout=10)
        resp.raise_for_status()
        text = resp.text.strip()

        # 解析JSONP格式: var quote_json = {...}
        # 去掉前缀和可能的前后空格/分号
        text = re.sub(r'^var\s+quote_json\s*=\s*', '', text)
        text = text.rstrip(';').strip()

        data = json.loads(text)

        if not data.get("flag", False):
            print(f"[ERROR] API返回flag=false: {data}")
            return None

        return data

    except requests.RequestException as e:
        print(f"[ERROR] 请求失败: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"[ERROR] JSON解析失败: {e}")
        return None


def _fmt(val, digits=2):
    """格式化数字"""
    if val is None or val == 0:
        return "--"
    if digits == 4:
        return f"{val:.4f}"
    return f"{val:.2f}"


def _fmt_time(timestamp_ms):
    """毫秒时间戳转 'YYYY-MM-DD HH:MM:SS'"""
    if not timestamp_ms:
        return "--"
    dt = datetime.fromtimestamp(timestamp_ms / 1000)
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def parse_all_prices(data):
    """
    从API返回数据中解析所有品种的价格信息
    返回格式化后的消息文本
    """
    if not data:
        return None

    result_parts = []

    # ========== 1. 金店-周大福 ==========
    ctf_gold = data.get(CODES["chowtaifook_gold"], {})
    ctf_bar = data.get(CODES["chowtaifook_bar"], {})

    ctf_gold_price = _fmt(ctf_gold.get("q63"))
    ctf_bar_price = _fmt(ctf_bar.get("q63"))
    ctf_time = _fmt_time(ctf_gold.get("time"))

    result_parts.append(
        f"金店-周大福\n"
        f"💰黄金价:(￥): {ctf_gold_price}\n"
        f"金条价: {ctf_bar_price}\n"
        f"单位: 元/克\n"
        f"更新时间: {ctf_time}"
    )

    # ========== 2. 银行-美元账户黄金 ==========
    usd_gold = data.get(CODES["bank_usd_gold"], {})

    usd_mid = _fmt(usd_gold.get("q69"), 4)
    usd_buy = _fmt(usd_gold.get("q74"), 4)   # 买入价
    usd_sell = _fmt(usd_gold.get("q73"), 4)   # 卖出价
    usd_high = _fmt(usd_gold.get("q71"), 4)
    usd_low = _fmt(usd_gold.get("q72"), 4)
    usd_time = _fmt_time(usd_gold.get("time"))

    result_parts.append(
        f"银行-美元账户黄金\n"
        f"🔥中间价($):  {usd_mid}\n"
        f"买入价: {usd_buy}\n"
        f"卖出价: {usd_sell}\n"
        f"最高价: {usd_high}\n"
        f"最低价: {usd_low}\n"
        f"更新时间: {usd_time}"
    )

    # ========== 3. 银行-人民币账户黄金 ==========
    cny_gold = data.get(CODES["bank_cny_gold"], {})

    cny_mid = _fmt(cny_gold.get("q69"))
    cny_buy = _fmt(cny_gold.get("q74"))
    cny_sell = _fmt(cny_gold.get("q73"))
    cny_high = _fmt(cny_gold.get("q71"))
    cny_low = _fmt(cny_gold.get("q72"))
    cny_time = _fmt_time(cny_gold.get("time"))

    result_parts.append(
        f"银行-人民币账户黄金\n"
        f"🏆中间价(￥): {cny_mid}\n"
        f"买入价: {cny_buy}\n"
        f"卖出价: {cny_sell}\n"
        f"最高价: {cny_high}\n"
        f"最低价: {cny_low}\n"
        f"更新时间: {cny_time}"
    )

    # ========== 4. 伦敦金 ==========
    london = data.get(CODES["london_gold"], {})

    london_price = _fmt(london.get("q63"))
    london_open = _fmt(london.get("q1"))
    london_high = _fmt(london.get("q3"))
    london_low = _fmt(london.get("q4"))
    london_prev = _fmt(london.get("q2"))
    london_time = _fmt_time(london.get("time"))

    result_parts.append(
        f"伦敦金\n"
        f"👍最新价:($): {london_price}\n"
        f"开盘价: {london_open}\n"
        f"最高价: {london_high}\n"
        f"最低价: {london_low}\n"
        f"昨收盘价: {london_prev}\n"
        f"更新时间: {london_time}"
    )

    # ========== 5. 上海-AU99.99 ==========
    sh = data.get(CODES["shanghai_9999"], {})

    sh_price = _fmt(sh.get("q63"))
    sh_open = _fmt(sh.get("q1"))
    sh_high = _fmt(sh.get("q3"))
    sh_low = _fmt(sh.get("q4"))
    sh_change_pct = sh.get("q80")
    sh_change_str = f"{sh_change_pct:.2f}" if sh_change_pct else "--"
    sh_prev = _fmt(sh.get("q2"))
    sh_volume = _fmt(sh.get("q60"))
    sh_time = _fmt_time(sh.get("time"))

    result_parts.append(
        f"上海-AU99.99\n"
        f"🚀当前价:(￥): {sh_price}\n"
        f"开盘价: {sh_open}\n"
        f"最高价: {sh_high}\n"
        f"最低价: {sh_low}\n"
        f"涨跌幅: {sh_change_str}\n"
        f"昨日收盘价: {sh_prev}\n"
        f"总成交量: {sh_volume}\n"
        f"更新时间: {sh_time}"
    )

    return "\n \n".join(result_parts)


def get_gold_price_message():
    """
    主入口：获取黄金价格并返回格式化消息
    """
    data = fetch_realtime_data()
    if not data:
        return None
    return parse_all_prices(data)


if __name__ == "__main__":
    msg = get_gold_price_message()
    if msg:
        print(msg)
    else:
        print("获取数据失败")
