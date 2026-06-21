import aiosmtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from jinja2 import Environment, FileSystemLoader, select_autoescape
from pathlib import Path
import asyncio

from src.config import settings
from src.core.logging import logger

TEMPLATES_DIR = Path(__file__).parent.parent / "templates"

class EmailService:
    def __init__(self):
        self.env = Environment(
            loader=FileSystemLoader(str(TEMPLATES_DIR)),
            autoescape=select_autoescape(['html', 'xml'])
        )

    async def send_email(self, to_email: str, subject: str, body: str):
        if settings.USE_MOCK_EMAIL:
            # Local development / Testing mock mode
            logger.info("---------------- [MOCK EMAIL SENT] ----------------")
            logger.info(f"To:      {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body (HTML):")
            logger.info(body)
            logger.info("---------------------------------------------------")
            return

        message = MIMEMultipart("alternative")
        message["From"] = settings.SMTP_FROM_EMAIL
        message["To"] = to_email
        message["Subject"] = subject

        part = MIMEText(body, "html")
        message.attach(part)

        logger.info(f"Sending SMTP email to {to_email} with subject: {subject}")
        try:
            # Use TLS for standard port 587 or if hostname isn't localhost
            use_tls = False
            start_tls = settings.SMTP_PORT == 587

            await aiosmtplib.send(
                message,
                hostname=settings.SMTP_HOST,
                port=settings.SMTP_PORT,
                username=settings.SMTP_USER,
                password=settings.SMTP_PASSWORD,
                use_tls=use_tls,
                start_tls=start_tls
            )
            logger.info(f"Successfully sent email to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            raise ValueError(f"Email delivery failed: {str(e)}")

    async def send_verification_email(self, email: str, verification_link: str):
        template = self.env.get_template("email_verify.html")
        loop = asyncio.get_running_loop()
        html_content = await loop.run_in_executor(None, template.render, {"verification_link": verification_link, "email": email})
        await self.send_email(
            to_email=email,
            subject="Verify your email address",
            body=html_content
        )

    async def send_password_reset_email(self, email: str, reset_link: str):
        template = self.env.get_template("password_reset.html")
        loop = asyncio.get_running_loop()
        html_content = await loop.run_in_executor(None, template.render, {"reset_link": reset_link, "email": email})
        await self.send_email(
            to_email=email,
            subject="Reset your password",
            body=html_content
        )

email_service = EmailService()
