"""QR code generation and network utilities."""

import base64
import logging
import socket
from contextlib import closing
from io import BytesIO

import qrcode

logger = logging.getLogger(__name__)

# DNS servers to try for external IP detection
_DNS_SERVERS = [
    ("8.8.8.8", 80),  # Google
    ("1.1.1.1", 80),  # Cloudflare
    ("208.67.222.222", 80),  # OpenDNS
]


def generate_qr_code_base64(url: str) -> str:
    """Generate a QR code as a base64-encoded PNG string."""
    qr = qrcode.QRCode(version=1, box_size=10, border=4)
    qr.add_data(url)
    qr.make(fit=True)
    image = qr.make_image(fill_color="black", back_color="white")

    buffer = BytesIO()
    image.save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def get_external_ip() -> str | None:
    """Get the machine's external-facing IP address.

    Tries multiple DNS servers as fallback if one is unreachable.
    Returns None if all methods fail.
    """
    for dns_server, port in _DNS_SERVERS:
        try:
            with closing(
                socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            ) as sock:
                sock.settimeout(2.0)  # Don't hang forever
                sock.connect((dns_server, port))
                return sock.getsockname()[0]
        except OSError:
            continue

    # Fallback: try to get hostname-based IP
    try:
        hostname = socket.gethostname()
        ip = socket.gethostbyname(hostname)
        # Filter out localhost addresses
        if ip and not ip.startswith("127."):
            return ip
    except OSError:
        pass

    logger.warning("Could not determine external IP address")
    return None


def build_join_url(host_header: str, pin: str) -> str:
    """Build the participant join URL, replacing localhost with external IP if needed."""
    host = host_header
    if "localhost" in host or "127.0.0.1" in host:
        if external_ip := get_external_ip():
            port = host.split(":")[-1] if ":" in host else "8000"
            host = f"{external_ip}:{port}"
        else:
            logger.warning(
                "Using localhost in join URL - participants on other devices "
                "may not be able to connect"
            )
    return f"http://{host}/quiz?pin={pin}"
