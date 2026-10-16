"""Startup environment loading tests.

Regression guard for: variables defined in ``.env`` (e.g. OPENAI_API_KEY)
must reach the process environment so the OpenAI client can find them.
"""

import os

from repair_ai.main import load_environment


def test_load_environment_imports_dotenv_values(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("REPAIR_AI_TEST_DOTENV_VAR=from-dotenv\n")
    monkeypatch.delenv("REPAIR_AI_TEST_DOTENV_VAR", raising=False)

    load_environment(str(env_file))

    assert os.environ["REPAIR_AI_TEST_DOTENV_VAR"] == "from-dotenv"


def test_real_environment_takes_precedence_over_dotenv(tmp_path, monkeypatch):
    env_file = tmp_path / ".env"
    env_file.write_text("REPAIR_AI_TEST_DOTENV_VAR=from-dotenv\n")
    monkeypatch.setenv("REPAIR_AI_TEST_DOTENV_VAR", "from-environment")

    load_environment(str(env_file))

    assert os.environ["REPAIR_AI_TEST_DOTENV_VAR"] == "from-environment"
