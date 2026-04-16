#!/usr/bin/env python3
"""调试飞书 WebSocket 连接 — 测试是否能收到消息"""

import os
import sys
import json
import asyncio
import signal

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Load .env
env_path = os.path.expanduser("~/.maxbot/.env")
if os.path.exists(env_path):
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, _, value = line.partition("=")
                os.environ.setdefault(key.strip(), value.strip())

import lark_oapi as lark
from lark_oapi.event.dispatcher_handler import EventDispatcherHandler
from lark_oapi.ws import Client as FeishuWSClient

app_id = os.environ.get("FEISHU_APP_ID", "")
app_secret = os.environ.get("FEISHU_APP_SECRET", "")

print(f"App ID: {app_id}")
print(f"App Secret: {'***' if app_secret else '(empty)'}")

received_events = []

def on_message(ctx, event):
    print(f"\n✅ 收到消息事件!")
    print(f"  event type: {type(event)}")
    try:
        msg = event.event.message
        sender = event.event.sender.sender_id.open_id
        print(f"  sender: {sender}")
        print(f"  chat_type: {msg.chat_type}")
        print(f"  message_type: {msg.message_type}")
        print(f"  message_id: {msg.message_id}")
        print(f"  chat_id: {msg.chat_id}")
        content = json.loads(msg.content) if msg.content else {}
        print(f"  content: {content}")
    except Exception as e:
        print(f"  解析失败: {e}")
        print(f"  raw event: {event}")
    received_events.append(event)

def on_any_event(ctx, event):
    print(f"\n📢 任意事件: {type(event)} - {getattr(event, 'event', 'N/A')}")

# Build handler
handler = EventDispatcherHandler.builder("", "").register_p2_im_message_receive_v1(on_message).build()

# Create client
client = FeishuWSClient(
    app_id=app_id,
    app_secret=app_secret,
    event_handler=handler,
    log_level=lark.LogLevel.DEBUG,
)

print("\n启动飞书 WebSocket (等待 30 秒检测消息)...")
print("请在飞书给机器人发一条消息\n")

import threading
t = threading.Thread(target=client.start, daemon=True)
t.start()

try:
    import time
    for i in range(30):
        time.sleep(1)
        if received_events:
            print(f"\n收到 {len(received_events)} 条消息")
            break
    else:
        print("\n⚠️ 30秒内未收到任何消息")
        print("可能原因:")
        print("  1. 飞书应用未开启「接收消息」事件")
        print("  2. 飞书应用未发布/审核")
        print("  3. 机器人未被添加到聊天")
except KeyboardInterrupt:
    pass

print("\n调试结束")
