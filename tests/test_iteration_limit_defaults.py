from maxbot.core.agent_loop import AgentConfig
from maxbot.config.config_loader import load_config



def test_default_iteration_limit_is_140():
    config = AgentConfig()
    assert config.max_iterations == 140



def test_yaml_default_iteration_limit_is_140():
    config = load_config()
    assert config.iteration.max_iterations == 140
