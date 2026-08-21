import pytest

from app.services.cloud_transport import gateway_api_url


@pytest.mark.parametrize(
    ("base", "expected"),
    [
        ("https://gateway.example.com", "https://gateway.example.com/api/cloud/sync/commands"),
        ("https://gateway.example.com/", "https://gateway.example.com/api/cloud/sync/commands"),
        ("https://gateway.example.com/api", "https://gateway.example.com/api/cloud/sync/commands"),
        ("https://gateway.example.com/api/", "https://gateway.example.com/api/cloud/sync/commands"),
    ],
)
def test_gateway_api_url_accepts_host_or_api_root(base: str, expected: str) -> None:
    assert gateway_api_url(base, "/cloud/sync/commands") == expected


def test_gateway_api_url_rejects_empty_base() -> None:
    with pytest.raises(ValueError, match="Cloud gateway base URL is required"):
        gateway_api_url("  ", "/cloud/sync/commands")
