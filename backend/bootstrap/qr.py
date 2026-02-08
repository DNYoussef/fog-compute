"""
QR Code Generation
==================

FOG-INSTALL-005: QR code generation for mesh invite links.

Generates QR codes in multiple formats (PNG base64, SVG) that encode
mesh invite URLs for easy device enrollment via camera scanning.

Features:
- PNG output (base64 encoded for API responses)
- SVG output (for web embedding)
- Customizable size and error correction
- URL encoding with invite token and metadata
"""
from __future__ import annotations

import base64
import io
import logging
from typing import Optional
from urllib.parse import urlencode, urljoin

try:
    import qrcode
    from qrcode.image.svg import SvgImage
    from qrcode.constants import ERROR_CORRECT_L, ERROR_CORRECT_M, ERROR_CORRECT_Q, ERROR_CORRECT_H
    HAS_QRCODE = True
except ImportError:
    HAS_QRCODE = False
    # Provide stubs for type checking
    ERROR_CORRECT_L = 1
    ERROR_CORRECT_M = 0
    ERROR_CORRECT_Q = 3
    ERROR_CORRECT_H = 2

logger = logging.getLogger(__name__)


class QRCodeGeneratorError(Exception):
    """Exception raised for QR code generation errors."""
    pass


class QRCodeGenerator:
    """
    QR code generation service for mesh invites.

    Generates QR codes that encode mesh invite URLs with tokens
    and metadata for easy device onboarding.
    """

    # Error correction levels
    ERROR_CORRECT_LOW = ERROR_CORRECT_L       # 7% of data can be restored
    ERROR_CORRECT_MEDIUM = ERROR_CORRECT_M    # 15% of data can be restored
    ERROR_CORRECT_QUARTILE = ERROR_CORRECT_Q  # 25% of data can be restored
    ERROR_CORRECT_HIGH = ERROR_CORRECT_H      # 30% of data can be restored

    def __init__(
        self,
        base_url: str = "http://localhost:8000",
        default_box_size: int = 10,
        default_border: int = 4,
        error_correction: int = ERROR_CORRECT_M,
    ):
        """
        Initialize the QR code generator.

        Args:
            base_url: Base URL for the bootstrap server
            default_box_size: Size of each QR code box in pixels
            default_border: Size of border in boxes
            error_correction: Error correction level
        """
        if not HAS_QRCODE:
            logger.warning("qrcode library not installed - QR generation will use fallback")

        self.base_url = base_url.rstrip('/')
        self.default_box_size = default_box_size
        self.default_border = default_border
        self.error_correction = error_correction

    def generate_invite_url(
        self,
        invite_token: str,
        mesh_name: str,
        intended_role: str = "worker",
    ) -> str:
        """
        Generate the full invite URL.

        Args:
            invite_token: The unique invite token
            mesh_name: Name of the mesh network
            intended_role: Role for the joining device

        Returns:
            Full URL for mesh joining
        """
        # Build query parameters
        params = {
            "token": invite_token,
            "mesh": mesh_name,
            "role": intended_role,
        }

        # Construct URL
        base = urljoin(self.base_url, "/api/v1/bootstrap/register")
        return f"{base}?{urlencode(params)}"

    def generate_png_base64(
        self,
        data: str,
        box_size: Optional[int] = None,
        border: Optional[int] = None,
    ) -> str:
        """
        Generate a QR code as a base64-encoded PNG.

        Args:
            data: The data to encode in the QR code
            box_size: Size of each box in pixels (optional)
            border: Size of border in boxes (optional)

        Returns:
            Base64-encoded PNG image string

        Raises:
            QRCodeGeneratorError: If generation fails
        """
        if not HAS_QRCODE:
            return self._generate_fallback_base64(data)

        try:
            qr = qrcode.QRCode(
                version=None,  # Auto-size
                error_correction=self.error_correction,
                box_size=box_size or self.default_box_size,
                border=border or self.default_border,
            )

            qr.add_data(data)
            qr.make(fit=True)

            # Create image
            img = qr.make_image(fill_color="black", back_color="white")

            # Convert to base64
            buffer = io.BytesIO()
            img.save(buffer, format='PNG')
            buffer.seek(0)

            base64_str = base64.b64encode(buffer.getvalue()).decode('ascii')

            logger.debug(f"Generated PNG QR code for data length {len(data)}")

            return base64_str

        except Exception as e:
            logger.error(f"Failed to generate PNG QR code: {e}")
            raise QRCodeGeneratorError(f"PNG generation failed: {e}")

    def generate_svg(
        self,
        data: str,
        box_size: Optional[int] = None,
        border: Optional[int] = None,
    ) -> str:
        """
        Generate a QR code as an SVG string.

        Args:
            data: The data to encode in the QR code
            box_size: Size of each box in pixels (optional)
            border: Size of border in boxes (optional)

        Returns:
            SVG markup string

        Raises:
            QRCodeGeneratorError: If generation fails
        """
        if not HAS_QRCODE:
            return self._generate_fallback_svg(data)

        try:
            qr = qrcode.QRCode(
                version=None,
                error_correction=self.error_correction,
                box_size=box_size or self.default_box_size,
                border=border or self.default_border,
            )

            qr.add_data(data)
            qr.make(fit=True)

            # Create SVG image
            factory = SvgImage
            img = qr.make_image(image_factory=factory)

            # Convert to string
            buffer = io.BytesIO()
            img.save(buffer)
            buffer.seek(0)

            svg_str = buffer.getvalue().decode('utf-8')

            logger.debug(f"Generated SVG QR code for data length {len(data)}")

            return svg_str

        except Exception as e:
            logger.error(f"Failed to generate SVG QR code: {e}")
            raise QRCodeGeneratorError(f"SVG generation failed: {e}")

    def generate_invite_qr(
        self,
        invite_token: str,
        mesh_name: str,
        intended_role: str = "worker",
        box_size: Optional[int] = None,
        border: Optional[int] = None,
    ) -> tuple[str, str, str]:
        """
        Generate QR codes for a mesh invite.

        Args:
            invite_token: The unique invite token
            mesh_name: Name of the mesh network
            intended_role: Role for the joining device
            box_size: Size of each box in pixels (optional)
            border: Size of border in boxes (optional)

        Returns:
            Tuple of (invite_url, png_base64, svg_string)

        Raises:
            QRCodeGeneratorError: If generation fails
        """
        # Generate the invite URL
        invite_url = self.generate_invite_url(invite_token, mesh_name, intended_role)

        # Generate QR codes
        png_base64 = self.generate_png_base64(invite_url, box_size, border)
        svg_string = self.generate_svg(invite_url, box_size, border)

        return invite_url, png_base64, svg_string

    def _generate_fallback_base64(self, data: str) -> str:
        """
        Generate a placeholder base64 string when qrcode library is not available.

        This creates a minimal valid PNG that indicates QR generation is unavailable.
        """
        # Minimal 1x1 white PNG (placeholder)
        placeholder_png = (
            b'\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01'
            b'\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde\x00'
            b'\x00\x00\x0cIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe\x02'
            b'\xfe\xdc\xccY\xe7\x00\x00\x00\x00IEND\xaeB`\x82'
        )
        return base64.b64encode(placeholder_png).decode('ascii')

    def _generate_fallback_svg(self, data: str) -> str:
        """
        Generate a placeholder SVG when qrcode library is not available.
        """
        return '''<?xml version="1.0" encoding="UTF-8"?>
<svg xmlns="http://www.w3.org/2000/svg" width="100" height="100">
  <rect width="100" height="100" fill="#fff"/>
  <text x="50" y="50" text-anchor="middle" fill="#999" font-size="10">
    QR Unavailable
  </text>
</svg>'''

    def set_base_url(self, base_url: str) -> None:
        """Update the base URL for invite generation."""
        self.base_url = base_url.rstrip('/')


# Module-level singleton instance
_qr_generator: Optional[QRCodeGenerator] = None


def get_qr_generator() -> QRCodeGenerator:
    """Get the singleton QRCodeGenerator instance."""
    global _qr_generator
    if _qr_generator is None:
        _qr_generator = QRCodeGenerator()
    return _qr_generator


def configure_qr_generator(base_url: str) -> QRCodeGenerator:
    """Configure and return the QR generator with custom base URL."""
    global _qr_generator
    _qr_generator = QRCodeGenerator(base_url=base_url)
    return _qr_generator
