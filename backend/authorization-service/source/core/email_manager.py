# source/core/email_manager.py
import os
import requests
import logging
from typing import Dict, Any
from jinja2 import Environment, FileSystemLoader

from source.core.base_manager import BaseManager
from source.utils.tracing import optional_trace_span

logger = logging.getLogger('email_manager')

class EmailManager(BaseManager):
    def __init__(self, db_manager=None):
        super().__init__(db_manager)
        
        # Mailgun configuration
        self.mailgun_enabled = os.getenv('EMAIL_ENABLED', 'true').lower() == 'true'
        self.mailgun_api_key = os.getenv('MAILGUN_API_KEY', 'API_KEY')
        self.mailgun_domain = os.getenv('MAILGUN_DOMAIN', 'sandbox5cecb1e74c8f456eb39118a09f6d5139.mailgun.org')
        self.mailgun_base_url = f"https://api.mailgun.net/v3/{self.mailgun_domain}"
        self.mailgun_sender = os.getenv('MAILGUN_SENDER', f"Trading Platform <postmaster@{self.mailgun_domain}>")
        
        # App configuration
        self.base_url = os.getenv('APP_BASE_URL', 'https://example.com')
        
        # Set up template engine
        template_dir = os.path.join(os.path.dirname(__file__), '../templates/email')
        self.template_env = Environment(loader=FileSystemLoader(template_dir))

    async def send_email(self, recipient_email: str, subject: str, template_name: str, context: Dict[str, Any]) -> bool:
        """Send an email using the Mailgun API"""
        with optional_trace_span(self.tracer, "send_email") as span:
            span.set_attribute("template", template_name)
            span.set_attribute("recipient", recipient_email)
            
            try:
                # Render template
                template = self.template_env.get_template(f"{template_name}.html")
                html_content = template.render(
                    **context,
                    base_url=self.base_url
                )
                
                # Create text version (simplified)
                text_content = f"{subject}\n\nPlease view this email in an HTML-compatible email client."
                
                if not self.mailgun_enabled:
                    logger.info(f"Email sending disabled. Would have sent to {recipient_email}:")
                    logger.info(f"Subject: {subject}")
                    logger.info(f"Content: {html_content[:200]}...")
                    span.set_attribute("email_sent", False)
                    span.set_attribute("email_disabled", True)
                    return True
                
                # Send via Mailgun API
                response = requests.post(
                    f"{self.mailgun_base_url}/messages",
                    auth=("api", self.mailgun_api_key),
                    data={
                        "from": self.mailgun_sender,
                        "to": recipient_email,
                        "subject": subject,
                        "text": text_content,
                        "html": html_content
                    }
                )
                
                if response.status_code == 200:
                    logger.info(f"Email sent to {recipient_email}, template: {template_name}")
                    span.set_attribute("email_sent", True)
                    span.set_attribute("mailgun_response", response.status_code)
                    return True
                else:
                    logger.error(f"Mailgun API error: {response.status_code} - {response.text}")
                    span.set_attribute("email_sent", False)
                    span.set_attribute("mailgun_error", response.text)
                    span.set_attribute("mailgun_status", response.status_code)
                    return False
                    
            except Exception as e:
                logger.error(f"Failed to send email: {e}")
                span.record_exception(e)
                span.set_attribute("error", str(e))
                return False

    async def send_verification_email(self, email: str, username: str, verification_code: str) -> bool:
        """Send email verification code"""
        with optional_trace_span(self.tracer, "send_verification_email") as span:
            span.set_attribute("username", username)
            
            subject = "Verify Your Email Address"
            context = {
                "username": username,
                "verification_code": verification_code,
                "app_name": "Trading Platform"
            }
            
            return await self.send_email(email, subject, "verification", context)

    async def send_forgot_username_email(self, email: str, username: str) -> bool:
        """Send username reminder email"""
        with optional_trace_span(self.tracer, "send_forgot_username_email") as span:
            
            subject = "Your Username Reminder"
            context = {
                "username": username,
                "app_name": "Trading Platform" 
            }
            
            return await self.send_email(email, subject, "username_reminder", context)

    async def send_password_reset_email(self, email: str, username: str, reset_token: str) -> bool:
        """Send password reset email"""
        with optional_trace_span(self.tracer, "send_password_reset_email") as span:
            span.set_attribute("username", username)
            
            reset_link = f"{self.base_url}/reset-password?token={reset_token}"
            subject = "Reset Your Password"
            context = {
                "username": username,
                "reset_link": reset_link,
                "app_name": "Trading Platform"
            }
            
            return await self.send_email(email, subject, "password_reset", context)