import importlib.util
import itertools
import sys
import types
from pathlib import Path

import pytest


PROJECT_ROOT = Path(__file__).resolve().parent.parent
START_GATEWAY_PATH = PROJECT_ROOT / "scripts" / "start_gateway.py"
_MODULE_COUNTER = itertools.count()


def _install_fake_start_gateway_dependencies(monkeypatch, *, gateway_server_module: types.ModuleType):
    fake_maxbot = types.ModuleType("maxbot")
    fake_maxbot.__path__ = []
    fake_gateway_pkg = types.ModuleType("maxbot.gateway")
    fake_gateway_pkg.__path__ = []
    fake_channels_pkg = types.ModuleType("maxbot.gateway.channels")
    fake_channels_pkg.__path__ = []

    fake_core = types.ModuleType("maxbot.core")

    class DummyAgent:
        pass

    class DummyAgentConfig:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    fake_core.Agent = DummyAgent
    fake_core.AgentConfig = DummyAgentConfig

    fake_tools = types.ModuleType("maxbot.tools")
    fake_tools.registry = []

    fake_base = types.ModuleType("maxbot.gateway.channels.base")

    class InboundMessage:
        pass

    class OutboundMessage:
        def __init__(self, **kwargs):
            self.kwargs = kwargs

    class MessageType:
        TEXT = "text"

    fake_base.InboundMessage = InboundMessage
    fake_base.OutboundMessage = OutboundMessage
    fake_base.MessageType = MessageType

    fake_fastapi = types.ModuleType("fastapi")

    class FastAPI:
        pass

    class Request:
        pass

    fake_fastapi.FastAPI = FastAPI
    fake_fastapi.Request = Request

    fake_uvicorn = types.ModuleType("uvicorn")
    fake_uvicorn.calls = []

    def fake_run(app, host, port, log_level):
        fake_uvicorn.calls.append(
            {
                "app": app,
                "host": host,
                "port": port,
                "log_level": log_level,
            }
        )

    fake_uvicorn.run = fake_run

    monkeypatch.setitem(sys.modules, "maxbot", fake_maxbot)
    monkeypatch.setitem(sys.modules, "maxbot.core", fake_core)
    monkeypatch.setitem(sys.modules, "maxbot.tools", fake_tools)
    monkeypatch.setitem(sys.modules, "maxbot.gateway", fake_gateway_pkg)
    monkeypatch.setitem(sys.modules, "maxbot.gateway.server", gateway_server_module)
    monkeypatch.setitem(sys.modules, "maxbot.gateway.channels", fake_channels_pkg)
    monkeypatch.setitem(sys.modules, "maxbot.gateway.channels.base", fake_base)
    monkeypatch.setitem(sys.modules, "fastapi", fake_fastapi)
    monkeypatch.setitem(sys.modules, "uvicorn", fake_uvicorn)

    return fake_uvicorn


def _load_start_gateway_module(monkeypatch, *, gateway_server_module: types.ModuleType):
    fake_uvicorn = _install_fake_start_gateway_dependencies(
        monkeypatch,
        gateway_server_module=gateway_server_module,
    )
    module_name = f"maxbot_start_gateway_test_{next(_MODULE_COUNTER)}"
    spec = importlib.util.spec_from_file_location(module_name, START_GATEWAY_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec is not None and spec.loader is not None
    spec.loader.exec_module(module)
    return module, fake_uvicorn


def test_start_gateway_import_does_not_require_module_level_app(monkeypatch):
    gateway_server_module = types.ModuleType("maxbot.gateway.server")

    class DummyGateway:
        def __init__(self, config):
            self.config = config
            self.app = object()
            self._sessions = {}

    class DummyGatewayConfig:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs

    gateway_server_module.MaxBotGateway = DummyGateway
    gateway_server_module.GatewayConfig = DummyGatewayConfig

    _load_start_gateway_module(monkeypatch, gateway_server_module=gateway_server_module)


def test_start_gateway_main_uses_server_app_for_uvicorn(monkeypatch, tmp_path):
    gateway_server_module = types.ModuleType("maxbot.gateway.server")
    app_sentinel = object()

    class DummyGateway:
        instances = []

        def __init__(self, config):
            self.config = config
            self.app = app_sentinel
            self._sessions = {}
            DummyGateway.instances.append(self)

    class DummyGatewayConfig:
        def __init__(self, *args, **kwargs):
            self.args = args
            self.kwargs = kwargs
            self.port = kwargs.get("port")
            self.agent_config = kwargs.get("agent_config")

    gateway_server_module.MaxBotGateway = DummyGateway
    gateway_server_module.GatewayConfig = DummyGatewayConfig

    module, fake_uvicorn = _load_start_gateway_module(
        monkeypatch,
        gateway_server_module=gateway_server_module,
    )

    monkeypatch.setattr(module, "load_env", lambda: None)
    monkeypatch.setenv("MAXBOT_API_KEY", "test-api-key")
    monkeypatch.setenv("MAXBOT_BASE_URL", "https://example.invalid/api")
    monkeypatch.setenv("MAXBOT_MODEL", "glm-4.7")
    monkeypatch.setenv("MAXBOT_PORT", "8765")
    monkeypatch.setattr(module.Path, "home", lambda: tmp_path)

    module.main()

    assert len(DummyGateway.instances) == 1
    assert fake_uvicorn.calls == [
        {
            "app": app_sentinel,
            "host": "0.0.0.0",
            "port": 8765,
            "log_level": "info",
        }
    ]
