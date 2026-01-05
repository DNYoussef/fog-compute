"""
Email Service
Handles sending emails for password reset and other notifications.
Supports SMTP and mock mode for testing.
"""
import logging
import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class EmailConfig:
    """Email configuration from environment variables"""
    smtp_host: str
    smtp_port: int
    smtp_user: str
    smtp_password: str
    from_email: str
    from_name: str
    mock_mode: bool


def get_email_config() -> EmailConfig:
    """Load email configuration from environment"""
    return EmailConfig(
        smtp_host=os.environ.get("SMTP_HOST", "localhost"),
        smtp_port=int(os.environ.get("SMTP_PORT", "587")),
        smtp_user=os.environ.get("SMTP_USER", ""),
        smtp_password=os.environ.get("SMTP_PASSWORD", ""),
        from_email=os.environ.get("EMAIL_FROM", "noreply@fog-compute.io"),
        from_name=os.environ.get("EMAIL_FROM_NAME", "Fog Compute"),
        mock_mode=os.environ.get("EMAIL_MOCK_MODE", "true").lower() == "true"
    )


class EmailService:
    """
    Service for sending emails.
    Supports SMTP delivery or mock mode for testing.
    """

    def __init__(self, config: Optional[EmailConfig] = None):
        self.config = config or get_email_config()
        self._sent_emails: list = []  # For testing - stores sent emails in mock mode

    async def send_password_reset_email(
        self,
        to_email: str,
        reset_token: str,
        username: str
    ) -> bool:
        """
        Send password reset email.

        Args:
            to_email: Recipient email address
            reset_token: Password reset token
            username: User's username for personalization

        Returns:
            True if email sent successfully
        """
        frontend_url = os.environ.get("FRONTEND_URL", "http://localhost:3000")
        reset_url = f"{frontend_url}/reset-password?token={reset_token}"

        subject = "Password Reset Request - Fog Compute"
        html_body = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <style>
                body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
                .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
                .header {{ background: #2563eb; color: white; padding: 20px; text-align: center; }}
                .content {{ padding: 30px; background: #f9fafb; }}
                .button {{ display: inline-block; padding: 12px 24px; background: #2563eb;
                          color: white; text-decoration: none; border-radius: 6px; margin: 20px 0; }}
                .footer {{ padding: 20px; text-align: center; color: #6b7280; font-size: 12px; }}
                .warning {{ background: #fef3c7; border-left: 4px solid #f59e0b; padding: 15px; margin: 20px 0; }}
            </style>
        </head>
        <body>
            <div class="container">
                <div class="header">
                    <h1>Fog Compute</h1>
                </div>
                <div class="content">
                    <h2>Password Reset Request</h2>
                    <p>Hello {username},</p>
                    <p>We received a request to reset the password for your Fog Compute account.</p>
                    <p>Click the button below to reset your password:</p>
                    <a href="{reset_url}" class="button">Reset Password</a>
                    <div class="warning">
                        <strong>Important:</strong>
                        <ul>
                            <li>This link will expire in 60 minutes</li>
                            <li>If you didn't request this reset, please ignore this email</li>
                            <li>Your password won't change unless you click the link and create a new one</li>
                        </ul>
                    </div>
                    <p>If the button doesn't work, copy and paste this URL into your browser:</p>
                    <p style="word-break: break-all; color: #6b7280;">{reset_url}</p>
                </div>
                <div class="footer">
                    <p>Fog Compute - Distributed Computing Platform</p>
                    <p>This is an automated message. Please do not reply directly to this email.</p>
                </div>
            </div>
        </body>
        </html>
        """

        text_body = f"""
        Password Reset Request - Fog Compute

        Hello {username},

        We received a request to reset the password for your Fog Compute account.

        To reset your password, visit this link:
        {reset_url}

        IMPORTANT:
        - This link will expire in 60 minutes
        - If you didn't request this reset, please ignore this email
        - Your password won't change unless you click the link and create a new one

        ---
        Fog Compute - Distributed Computing Platform
        This is an automated message. Please do not reply directly to this email.
        """

        return await self._send_email(
            to_email=to_email,
            subject=subject,
            html_body=html_body,
            text_body=text_body
        )

    async def _send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str
    ) -> bool:
        """
        Send an email.

        Args:
            to_email: Recipient email
            subject: Email subject
            html_body: HTML body content
            text_body: Plain text body content

        Returns:
            True if sent successfully
        """
        if self.config.mock_mode:
            # Mock mode - store email for testing
            self._sent_emails.append({
                "to": to_email,
                "subject": subject,
                "html_body": html_body,
                "text_body": text_body
            })
            logger.info(f"[MOCK] Email sent to {to_email}: {subject}")
            return True

        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subject
            msg["From"] = f"{self.config.from_name} <{self.config.from_email}>"
            msg["To"] = to_email

            # Attach both text and HTML versions
            msg.attach(MIMEText(text_body, "plain"))
            msg.attach(MIMEText(html_body, "html"))

            # Connect and send
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                if self.config.smtp_user and self.config.smtp_password:
                    server.login(self.config.smtp_user, self.config.smtp_password)
                server.sendmail(self.config.from_email, to_email, msg.as_string())

            logger.info(f"Email sent to {to_email}: {subject}")
            return True

        except smtplib.SMTPAuthenticationError as e:
            logger.error(f"SMTP authentication failed: {e}")
            return False
        except smtplib.SMTPException as e:
            logger.error(f"SMTP error sending email: {e}")
            return False
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False

    def get_sent_emails(self) -> list:
        """Get list of sent emails (mock mode only)"""
        return self._sent_emails

    def clear_sent_emails(self):
        """Clear sent emails list (for testing)"""
        self._sent_emails = []


# Global singleton instance
email_service = EmailService()


def get_email_service() -> EmailService:
    """Get email service instance"""
    return email_service
