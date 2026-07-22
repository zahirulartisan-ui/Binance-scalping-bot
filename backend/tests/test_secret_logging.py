from app.core.settings import Settings


def test_secret_values_are_not_serialized_for_logging() -> None:
    settings = Settings(
        binance_demo_api_key="actual-api-token",
        binance_demo_api_secret="actual-secret-token",
        binance_api_key="actual-live-api-token",
        binance_api_secret="actual-live-secret-token",
    )

    rendered = str(settings.model_dump())

    assert "actual-api-token" not in rendered
    assert "actual-secret-token" not in rendered
    assert "actual-live-api-token" not in rendered
    assert "actual-live-secret-token" not in rendered
