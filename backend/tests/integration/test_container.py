import os
from pathlib import Path

import pytest
from pydantic import SecretStr

from compileit_chat.config import Settings
from compileit_chat.container import ConfigurationError, Container


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Tracing writes os.environ; give each test its own copy without LangSmith variables."""
    environment = {k: v for k, v in os.environ.items() if not k.startswith("LANGSMITH_")}
    monkeypatch.setattr(os, "environ", environment)


def test_langsmith_tracing_is_exported_for_langchain() -> None:
    Container(
        Settings(
            _env_file=None,
            langsmith_tracing=True,
            langsmith_api_key=SecretStr("ls-key"),
            langsmith_project="eval",
        )
    )

    assert os.environ["LANGSMITH_TRACING"] == "true"
    assert os.environ["LANGSMITH_PROJECT"] == "eval"


def test_tracing_without_key_is_a_configuration_error() -> None:
    with pytest.raises(ConfigurationError, match="LANGSMITH_API_KEY"):
        Container(Settings(_env_file=None, langsmith_tracing=True))


def test_missing_openai_key_is_reported_when_a_model_is_needed() -> None:
    container = Container(Settings(_env_file=None, openai_api_key=None))

    with pytest.raises(ConfigurationError, match="No OpenAI API key"):
        _ = container.embeddings


async def test_openai_key_is_read_from_the_encrypted_database(tmp_path: Path) -> None:
    settings = Settings(
        _env_file=None,
        openai_api_key=None,  # nothing in the environment
        data_dir=tmp_path,
        secrets_master_key=SecretStr(Container.new_master_key()),
    )
    first = Container(settings)
    await first.start()
    await first.store_secret().execute("openai_api_key", "sk-from-database")
    await first.stop()

    restarted = Container(settings)
    await restarted.start()
    try:
        assert restarted._openai_api_key().get_secret_value() == "sk-from-database"
    finally:
        await restarted.stop()
