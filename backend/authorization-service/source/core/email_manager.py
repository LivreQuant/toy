# source/core/email_manager.py
import os
import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from jinja2 import Environment, FileSystemLoader

from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span


class EmailManager(BaseManager):
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        self.smtp_host = os.getenv('SMTP_HOST', 'smtp.example.com')
        self.smtp_port = int(os.getenv('SMTP_PORT', '587'))
        self.smtp_user = os.getenv('SMTP_USER', '')
        self.smtp_password = os.getenv('SMTP_PASSWORD', '')
        self.sender_email = os.getenv('SENDER_EMAIL', 'noreply@example.com')
        self.sender_name = os.getenv('SENDER_NAME', 'Authentication Service')
        self.base_url = os.getenv('APP_BASE_URL', 'https://example.com')

        # Set up template engine
        template_dir = os.path.join(os.path.dirname(__file__), '../templates/email')
        self.template_env = Environment(loader=FileSystemLoader(template_dir))

    async def send_email(self, recipient_email, subject, template_name, context):
        """Send an email using a template"""
        with optional_trace_span(self.tracer, "send_email") as span:
            span.set_attribute("template", template_name)
            span.set_attribute("recipient", recipient_email)

            try:
                # Prepare message
                message = MIMEMultipart("alternative")
                message["Subject"] = subject
                message["From"] = f"{self.sender_name} <{self.sender_email}>"
                message["To"] = recipient_email

                # Render template
                template = self.template_env.get_template(f"{template_name}.html")
                html_content = template.render(
                    **context,
                    base_url=self.base_url
                )

                # Add HTML part
                html_part = MIMEText(html_content, "html")
                message.attach(html_part)

                # Send email
                if os.getenv('EMAIL_ENABLED', 'true').lower() == 'true':
                    await aiosmtplib.send(
                        message,
                        hostname=self.smtp_host,
                        port=self.smtp_port,
                        username=self.smtp_user,
                        password=self.smtp_password,
                        use_tls=True
                    )
                    self.logger.info(f"Email sent to {recipient_email}, template: {template_name}")
                    span.set_attribute("email_sent", True)
                else:
                    # Log email content for development/testing
                    self.logger.info(f"Email sending disabled. Would have sent to {recipient_email}:")
                    self.logger.info(f"Subject: {subject}")
                    self.logger.info(f"Content: {html_content[:200]}...")
                    span.set_attribute("email_sent", False)
                    span.set_attribute("email_disabled", True)

                return True
            except Exception as e:
                self.logger.error(f"Failed to send email: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False

    async def send_verification_email(self, email, username, verification_code):
        """Send email verification code"""
        with optional_trace_span(self.tracer, "send_verification_email") as span:
            span.set_attribute("username", username)

            subject = "Verify Your Email Address"
            context = {
                "username": username,
                "verification_code": verification_code
            }

            return await self.send_email(email, subject, "verification", context)

    async def send_forgot_username_email(self, email, username):
        """Send username reminder email"""
        with optional_trace_span(self.tracer, "send_forgot_username_email") as span:
            subject = "Your Username Reminder"
            context = {
                "username": username
            }

            return await self.send_email(email, subject, "username_reminder", context)

    async def send_password_reset_email(self, email, username, reset_token):
        """Send password reset email"""
        with optional_trace_span(self.tracer, "send_password_reset_email") as span:
            span.set_attribute("username", username)

            reset_link = f"{self.base_url}/reset-password?token={reset_token}"
            subject = "Reset Your Password"
            context = {
                "username": username,
                "reset_link": reset_link
            }

            return await self.send_email(email, subject, "password_reset", context)
