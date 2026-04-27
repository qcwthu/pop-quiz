"""Tests for the qr module."""

import base64
from unittest.mock import patch

from pop_quiz.qr import build_join_url, generate_qr_code_base64


class TestGenerateQrCodeBase64:
    """Tests for QR code generation."""

    def test_returns_base64_string(self) -> None:
        """Should return a valid base64-encoded string."""
        result = generate_qr_code_base64("https://example.com")
        # Should be valid base64
        decoded = base64.b64decode(result)
        assert len(decoded) > 0

    def test_returns_png_image(self) -> None:
        """Should return a PNG image."""
        result = generate_qr_code_base64("https://example.com")
        decoded = base64.b64decode(result)
        # PNG files start with these magic bytes
        png_header = b"\x89PNG\r\n\x1a\n"
        assert decoded[:8] == png_header

    def test_different_urls_produce_different_qr(self) -> None:
        """Different URLs should produce different QR codes."""
        qr1 = generate_qr_code_base64("https://example.com/a")
        qr2 = generate_qr_code_base64("https://example.com/b")
        assert qr1 != qr2

    def test_same_url_produces_same_qr(self) -> None:
        """Same URL should produce identical QR codes."""
        qr1 = generate_qr_code_base64("https://example.com/test")
        qr2 = generate_qr_code_base64("https://example.com/test")
        assert qr1 == qr2


class TestBuildJoinUrl:
    """Tests for join URL building."""

    def test_external_host_unchanged(self) -> None:
        """External host should be used as-is."""
        url = build_join_url("192.168.1.100:8000", "123456")
        assert url == "http://192.168.1.100:8000/quiz?pin=123456"

    def test_includes_pin_parameter(self) -> None:
        """URL should include PIN as query parameter."""
        url = build_join_url("example.com:8000", "999999")
        assert "pin=999999" in url

    def test_localhost_replaced_with_external_ip(self) -> None:
        """Localhost should be replaced with external IP."""
        with patch("pop_quiz.qr.get_external_ip", return_value="10.0.0.50"):
            url = build_join_url("localhost:8000", "123456")
            assert "10.0.0.50:8000" in url
            assert "localhost" not in url

    def test_127_0_0_1_replaced_with_external_ip(self) -> None:
        """127.0.0.1 should be replaced with external IP."""
        with patch("pop_quiz.qr.get_external_ip", return_value="10.0.0.50"):
            url = build_join_url("127.0.0.1:8000", "123456")
            assert "10.0.0.50:8000" in url
            assert "127.0.0.1" not in url

    def test_localhost_kept_when_no_external_ip(self) -> None:
        """Localhost should be kept when external IP unavailable."""
        with patch("pop_quiz.qr.get_external_ip", return_value=None):
            url = build_join_url("localhost:8000", "123456")
            assert "localhost:8000" in url

    def test_preserves_port(self) -> None:
        """Should preserve the port number."""
        with patch("pop_quiz.qr.get_external_ip", return_value="10.0.0.50"):
            url = build_join_url("localhost:3000", "123456")
            assert ":3000" in url

    def test_default_port_when_missing(self) -> None:
        """Should use default port 8000 when not specified."""
        with patch("pop_quiz.qr.get_external_ip", return_value="10.0.0.50"):
            url = build_join_url("localhost", "123456")
            assert "10.0.0.50:8000" in url

    def test_uses_http_protocol(self) -> None:
        """URL should use HTTP protocol."""
        url = build_join_url("example.com:8000", "123456")
        assert url.startswith("http://")
