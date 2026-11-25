def test_token_encryption_roundtrip_and_tamper(client):
    from classroom.security import decrypt, encrypt
    enc = encrypt("1//refresh-token")
    assert enc != "1//refresh-token" and decrypt(enc) == "1//refresh-token"
    assert decrypt(enc[:-4] + "AAAA") is None


def test_short_secret_rejected(monkeypatch):
    import pytest
    from classroom import config
    monkeypatch.setenv("SECRET_KEY", "short")
    config.get_settings.cache_clear()
    with pytest.raises(RuntimeError):
        config.get_settings()
    config.get_settings.cache_clear()
