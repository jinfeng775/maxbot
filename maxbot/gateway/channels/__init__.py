"""MaxBot 渠道适配器"""

from maxbot.gateway.channels.base import (
    ChannelAdapter,
    ChannelRegistry,
    InboundMessage,
    MessageType,
    OutboundMessage,
)
from maxbot.gateway.channels.http_channel import HttpChannel
from maxbot.gateway.channels.telegram import TelegramChannel

__all__ = [
    "ChannelAdapter",
    "ChannelRegistry",
    "InboundMessage",
    "MessageType",
    "OutboundMessage",
    "HttpChannel",
    "TelegramChannel",
]
