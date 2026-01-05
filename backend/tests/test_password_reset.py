"""
TEST-01: Password Reset Unit Tests
Tests password reset flow including token generation, validation, and email service
"""
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from server.services.token_service import TokenService, PasswordResetTokenData
from server.services.email_service import EmailService, EmailConfig
from server.schemas.auth import PasswordResetRequest, PasswordResetConfirm, PasswordResetResponse


class TestPasswordResetTokenService:
    """Tests for password reset token management in TokenService"""

    @pytest.fixture
    def token_service(self):
        """Fresh TokenService instance"""
        return TokenService()

    @pytest.mark.asyncio
    async def test_create_password_reset_token(self, token_service):
        """Test creating a password reset token"""
        token_data = await token_service.create_password_reset_token(
            user_id="user-123",
            email="test@example.com"
        )

        assert isinstance(token_data, PasswordResetTokenData)
        assert token_data.user_id == "user-123"
        assert token_data.email == "test@example.com"
        assert len(token_data.token) > 20  # URL-safe token should be long
        assert token_data.expires_at > datetime.now(timezone.utc)
        assert token_data.used is False

    @pytest.mark.asyncio
    async def test_validate_password_reset_token_valid(self, token_service):
        """Test validating a valid password reset token"""
        # Create a token
        created_token = await token_service.create_password_reset_token(
            user_id="user-456",
            email="valid@example.com"
        )

        # Validate it
        validated = await token_service.validate_password_reset_token(created_token.token)

        assert validated is not None
        assert validated.user_id == "user-456"
        assert validated.email == "valid@example.com"

    @pytest.mark.asyncio
    async def test_validate_password_reset_token_invalid(self, token_service):
        """Test validating an invalid password reset token"""
        validated = await token_service.validate_password_reset_token("invalid-token-abc123")

        assert validated is None

    @pytest.mark.asyncio
    async def test_consume_password_reset_token(self, token_service):
        """Test consuming (using) a password reset token"""
        # Create a token
        created_token = await token_service.create_password_reset_token(
            user_id="user-789",
            email="consume@example.com"
        )

        # Consume it
        consumed = await token_service.consume_password_reset_token(created_token.token)
        assert consumed is True

        # Try to validate - should fail now (already consumed)
        validated = await token_service.validate_password_reset_token(created_token.token)
        assert validated is None

    @pytest.mark.asyncio
    async def test_consume_nonexistent_token(self, token_service):
        """Test consuming a nonexistent token returns False"""
        consumed = await token_service.consume_password_reset_token("nonexistent-token")
        assert consumed is False

    @pytest.mark.asyncio
    async def test_password_reset_token_single_use(self, token_service):
        """Test that password reset tokens can only be used once"""
        # Create a token
        created_token = await token_service.create_password_reset_token(
            user_id="user-single",
            email="single@example.com"
        )

        # First consumption should succeed
        first_consume = await token_service.consume_password_reset_token(created_token.token)
        assert first_consume is True

        # Second consumption should fail
        second_consume = await token_service.consume_password_reset_token(created_token.token)
        assert second_consume is False

    @pytest.mark.asyncio
    async def test_invalidate_user_reset_tokens(self, token_service):
        """Test invalidating all reset tokens for a user"""
        user_id = "user-multi-token"

        # Create multiple tokens for same user
        token1 = await token_service.create_password_reset_token(user_id, "email1@test.com")
        token2 = await token_service.create_password_reset_token(user_id, "email2@test.com")
        token3 = await token_service.create_password_reset_token("other-user", "other@test.com")

        # Invalidate all tokens for the user
        invalidated = await token_service.invalidate_user_reset_tokens(user_id)
        assert invalidated >= 2

        # User's tokens should be invalid now
        assert await token_service.validate_password_reset_token(token1.token) is None
        assert await token_service.validate_password_reset_token(token2.token) is None

        # Other user's token should still be valid
        assert await token_service.validate_password_reset_token(token3.token) is not None


class TestEmailService:
    """Tests for EmailService"""

    @pytest.fixture
    def mock_config(self):
        """Mock email config in mock mode"""
        return EmailConfig(
            smtp_host="localhost",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            from_email="noreply@test.com",
            from_name="Test",
            mock_mode=True
        )

    @pytest.fixture
    def email_service(self, mock_config):
        """Email service in mock mode"""
        return EmailService(config=mock_config)

    @pytest.mark.asyncio
    async def test_send_password_reset_email_success(self, email_service):
        """Test sending password reset email succeeds"""
        result = await email_service.send_password_reset_email(
            to_email="user@example.com",
            reset_token="test-reset-token-12345",
            username="testuser"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_send_password_reset_email_stored_in_mock(self, email_service):
        """Test that sent emails are stored in mock mode"""
        email_service.clear_sent_emails()

        await email_service.send_password_reset_email(
            to_email="user@example.com",
            reset_token="test-reset-token-12345",
            username="testuser"
        )

        sent = email_service.get_sent_emails()
        assert len(sent) == 1
        assert sent[0]["to"] == "user@example.com"
        assert "Password Reset" in sent[0]["subject"]
        assert "test-reset-token-12345" in sent[0]["html_body"]
        assert "testuser" in sent[0]["html_body"]

    @pytest.mark.asyncio
    async def test_email_contains_reset_link(self, email_service):
        """Test that reset email contains proper reset link"""
        email_service.clear_sent_emails()

        await email_service.send_password_reset_email(
            to_email="user@example.com",
            reset_token="abc123token",
            username="testuser"
        )

        sent = email_service.get_sent_emails()
        html_body = sent[0]["html_body"]

        # Should contain the token in URL
        assert "abc123token" in html_body
        assert "reset-password" in html_body

    @pytest.mark.asyncio
    async def test_email_contains_security_warning(self, email_service):
        """Test that reset email contains security warnings"""
        email_service.clear_sent_emails()

        await email_service.send_password_reset_email(
            to_email="user@example.com",
            reset_token="xyz789token",
            username="testuser"
        )

        sent = email_service.get_sent_emails()
        html_body = sent[0]["html_body"]

        # Should contain security warnings
        assert "expire" in html_body.lower() or "60 minutes" in html_body
        assert "ignore" in html_body.lower()

    def test_clear_sent_emails(self, email_service):
        """Test clearing sent emails list"""
        email_service._sent_emails = [{"to": "test@test.com"}]
        assert len(email_service.get_sent_emails()) == 1

        email_service.clear_sent_emails()
        assert len(email_service.get_sent_emails()) == 0


class TestPasswordResetSchemas:
    """Tests for password reset Pydantic schemas"""

    def test_password_reset_request_valid(self):
        """Test valid password reset request"""
        request = PasswordResetRequest(email="valid@example.com")
        assert request.email == "valid@example.com"

    def test_password_reset_request_invalid_email(self):
        """Test invalid email format raises error"""
        with pytest.raises(Exception):  # Pydantic validation error
            PasswordResetRequest(email="not-an-email")

    def test_password_reset_confirm_valid(self):
        """Test valid password reset confirm request"""
        confirm = PasswordResetConfirm(
            token="abcdefghijk123456789",
            new_password="ValidPass123"
        )
        assert confirm.token == "abcdefghijk123456789"
        assert confirm.new_password == "ValidPass123"

    def test_password_reset_confirm_weak_password_no_uppercase(self):
        """Test password without uppercase fails validation"""
        with pytest.raises(Exception):  # Pydantic validation error
            PasswordResetConfirm(
                token="abcdefghijk123456789",
                new_password="nouppercas1"
            )

    def test_password_reset_confirm_weak_password_no_lowercase(self):
        """Test password without lowercase fails validation"""
        with pytest.raises(Exception):
            PasswordResetConfirm(
                token="abcdefghijk123456789",
                new_password="NOLOWERCASE1"
            )

    def test_password_reset_confirm_weak_password_no_digit(self):
        """Test password without digit fails validation"""
        with pytest.raises(Exception):
            PasswordResetConfirm(
                token="abcdefghijk123456789",
                new_password="NoDigitsHere"
            )

    def test_password_reset_confirm_short_password(self):
        """Test short password fails validation"""
        with pytest.raises(Exception):
            PasswordResetConfirm(
                token="abcdefghijk123456789",
                new_password="Aa1"  # Too short
            )

    def test_password_reset_confirm_short_token(self):
        """Test short token fails validation"""
        with pytest.raises(Exception):
            PasswordResetConfirm(
                token="short",  # Less than 10 chars
                new_password="ValidPass123"
            )

    def test_password_reset_response(self):
        """Test password reset response schema"""
        response = PasswordResetResponse(message="Password reset successfully")
        assert response.message == "Password reset successfully"


class TestPasswordResetTokenExpiry:
    """Tests for password reset token expiration"""

    @pytest.fixture
    def token_service(self):
        """Fresh TokenService instance"""
        return TokenService()

    @pytest.mark.asyncio
    async def test_token_has_expiry(self, token_service):
        """Test that created token has expiry set"""
        token_data = await token_service.create_password_reset_token(
            user_id="user-exp",
            email="expiry@test.com"
        )

        assert token_data.expires_at is not None
        assert token_data.expires_at > datetime.now(timezone.utc)

    @pytest.mark.asyncio
    async def test_token_expires_in_approximately_60_minutes(self, token_service):
        """Test that token expires in approximately 60 minutes"""
        now = datetime.now(timezone.utc)
        token_data = await token_service.create_password_reset_token(
            user_id="user-60",
            email="sixty@test.com"
        )

        time_until_expiry = (token_data.expires_at - now).total_seconds()
        # Should be approximately 60 minutes (3600 seconds) +/- 10 seconds
        assert 3590 < time_until_expiry < 3610


class TestPasswordResetIntegration:
    """Integration-style tests for password reset flow"""

    @pytest.fixture
    def token_service(self):
        """Fresh TokenService instance"""
        return TokenService()

    @pytest.fixture
    def email_service(self):
        """Email service in mock mode"""
        config = EmailConfig(
            smtp_host="localhost",
            smtp_port=587,
            smtp_user="",
            smtp_password="",
            from_email="noreply@test.com",
            from_name="Test",
            mock_mode=True
        )
        return EmailService(config=config)

    @pytest.mark.asyncio
    async def test_full_reset_flow_token_lifecycle(self, token_service):
        """Test full password reset token lifecycle"""
        user_id = "user-full-flow"
        email = "fullflow@test.com"

        # 1. Create token
        token_data = await token_service.create_password_reset_token(user_id, email)
        token = token_data.token

        # 2. Validate token (as would happen when user clicks link)
        validated = await token_service.validate_password_reset_token(token)
        assert validated is not None
        assert validated.user_id == user_id

        # 3. Consume token (after password is successfully changed)
        consumed = await token_service.consume_password_reset_token(token)
        assert consumed is True

        # 4. Token should no longer be valid
        revalidated = await token_service.validate_password_reset_token(token)
        assert revalidated is None

    @pytest.mark.asyncio
    async def test_reset_flow_with_email(self, token_service, email_service):
        """Test password reset flow with email sending"""
        user_id = "user-email-flow"
        email = "emailflow@test.com"
        username = "emailflowuser"

        email_service.clear_sent_emails()

        # 1. Create token
        token_data = await token_service.create_password_reset_token(user_id, email)

        # 2. Send email
        sent = await email_service.send_password_reset_email(
            to_email=email,
            reset_token=token_data.token,
            username=username
        )
        assert sent is True

        # 3. Verify email was sent with token
        emails = email_service.get_sent_emails()
        assert len(emails) == 1
        assert token_data.token in emails[0]["html_body"]

        # 4. Validate and consume token
        validated = await token_service.validate_password_reset_token(token_data.token)
        assert validated is not None

        consumed = await token_service.consume_password_reset_token(token_data.token)
        assert consumed is True
