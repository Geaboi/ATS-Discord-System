from app.schemas.settings import SettingsOut, SettingsUpdate


def test_settings_out_includes_model_fields():
    s = SettingsOut(
        discord_webhook=None,
        score_threshold=0.65,
        scrape_interval=60,
        ollama_model="llama3.1:8b",
        ollama_scoring_model="llama3.2:3b",
    )
    assert s.ollama_model == "llama3.1:8b"
    assert s.ollama_scoring_model == "llama3.2:3b"


def test_settings_update_model_fields_optional():
    u = SettingsUpdate()
    assert u.ollama_model is None
    assert u.ollama_scoring_model is None
