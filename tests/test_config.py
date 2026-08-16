from ground_truth import config


def test_select_model_defaults_to_gemini(monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "x")
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    assert config.select_model() == config.DEFAULT_MODEL


def test_select_model_falls_back_to_groq(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.setenv("GROQ_API_KEY", "x")
    assert config.select_model() == config.FALLBACK_MODEL


def test_get_secret_reads_env(monkeypatch):
    monkeypatch.setenv("SOME_TEST_KEY", "value123")
    assert config.get_secret("SOME_TEST_KEY") == "value123"


def test_get_secret_missing_returns_none(monkeypatch):
    monkeypatch.delenv("TOTALLY_UNSET_KEY", raising=False)
    assert config.get_secret("TOTALLY_UNSET_KEY") is None
