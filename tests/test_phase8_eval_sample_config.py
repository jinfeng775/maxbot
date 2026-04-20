from pathlib import Path
from unittest.mock import patch

from maxbot.config.config_loader import ConfigLoader
from maxbot.core.agent_loop import AgentConfig


def _load_default_only_config(tmp_path: Path):
    loader = ConfigLoader(config_path=tmp_path / "missing-config.yaml")
    return loader.load()


def test_eval_sample_defaults_align_between_agent_config_and_loader(tmp_path: Path):
    config = _load_default_only_config(tmp_path)

    with patch("maxbot.core.agent_loop.get_config", return_value=config):
        agent_config = AgentConfig()

    assert config.session.eval_samples_enabled is False
    assert config.session.eval_sample_store_dir is None
    assert agent_config.eval_samples_enabled == config.session.eval_samples_enabled
    assert agent_config.eval_sample_store_dir == config.session.eval_sample_store_dir


def test_config_loader_applies_eval_sample_environment_overrides(monkeypatch, tmp_path: Path):
    sample_dir = tmp_path / "eval-samples"
    monkeypatch.setenv("MAXBOT_EVAL_SAMPLES_ENABLED", "true")
    monkeypatch.setenv("MAXBOT_EVAL_SAMPLE_STORE_DIR", str(sample_dir))

    config = _load_default_only_config(tmp_path)

    assert config.session.eval_samples_enabled is True
    assert config.session.eval_sample_store_dir == str(sample_dir)



def test_agent_config_loads_eval_sample_settings_from_config(tmp_path: Path):
    loader = ConfigLoader(config_path=tmp_path / "missing-config.yaml")
    config = loader.load_from_dict(
        {
            "session": {
                "eval_samples_enabled": True,
                "eval_sample_store_dir": str(tmp_path / "configured-samples"),
            }
        }
    )

    with patch("maxbot.core.agent_loop.get_config", return_value=config):
        agent_config = AgentConfig()

    assert agent_config.eval_samples_enabled is True
    assert agent_config.eval_sample_store_dir == str(tmp_path / "configured-samples")
