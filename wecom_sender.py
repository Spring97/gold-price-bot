#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
企业微信机器人推送模块
通过Webhook发送消息到企业微信群
"""

import requests
import json

# 企业微信机器人Webhook地址
WEBHOOK_URL = "https://qyapi.weixin.qq.com/cgi-bin/webhook/send?key=84969200-e386-4102-af8a-42e274ca5cb7"


def send_text_message(content):
    """
    发送text类型消息到企业微信群

    Args:
        content: 消息文本内容

    Returns:
        dict: API返回结果
    """
    payload = {
        "msgtype": "text",
        "text": {
            "content": content
        }
    }

    try:
        resp = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=10
        )
        result = resp.json()

        if result.get("errcode") == 0:
            print(f"[OK] 消息发送成功")
            return result
        else:
            print(f"[ERROR] 消息发送失败: {result}")
            return result

    except Exception as e:
        print(f"[ERROR] 发送异常: {e}")
        return None


def send_markdown_message(content):
    """
    发送markdown类型消息到企业微信群

    Args:
        content: Markdown格式消息内容

    Returns:
        dict: API返回结果
    """
    payload = {
        "msgtype": "markdown",
        "markdown": {
            "content": content
        }
    }

    try:
        resp = requests.post(
            WEBHOOK_URL,
            headers={"Content-Type": "application/json"},
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            timeout=10
        )
        result = resp.json()

        if result.get("errcode") == 0:
            print(f"[OK] Markdown消息发送成功")
            return result
        else:
            print(f"[ERROR] Markdown消息发送失败: {result}")
            return result

    except Exception as e:
        print(f"[ERROR] 发送异常: {e}")
        return None


if __name__ == "__main__":
    # 测试发送
    send_text_message("✅ 企业微信推送模块测试成功！")
