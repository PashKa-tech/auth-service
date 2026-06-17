import asyncio
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from src.config import settings
from src.core.logging import logger

class EmailService:
    async def send_email(self, to_email: str, subject: str, body: str) -> None:
        """Send an email asynchronously. Uses mock console logger in development/testing."""
        if settings.USE_MOCK_EMAIL:
            # Local development / Testing mock mode
            logger.info("---------------- [MOCK EMAIL SENT] ----------------")
            logger.info(f"To:      {to_email}")
            logger.info(f"Subject: {subject}")
            logger.info(f"Body:    {body}")
            logger.info("---------------------------------------------------")
            return

        # Production real SMTP mode - execute in thread pool to prevent blocking the async loop
        await asyncio.to_thread(self._send_smtp_email_sync, to_email, subject, body)

    def _send_smtp_email_sync(self, to_email: str, subject: str, body: str) -> None:
        """Synchronous SMTP send helper, meant to be run in a separate thread."""
        logger.info(f"Sending SMTP email to {to_email} with subject: {subject}")
        
        # Create message container
        msg = MIMEMultipart()
        msg["From"] = settings.SMTP_FROM_EMAIL
        msg["To"] = to_email
        msg["Subject"] = subject
        
        # Attach email body as HTML or text (default to html/plain)
        msg.attach(MIMEText(body, "html"))
        
        try:
            # Connect to SMTP server
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10) as server:
                # Start TLS if port is standard secure ports
                if settings.SMTP_PORT == 587:
                    server.starttls()
                
                # Authenticate if credentials are provided
                if settings.SMTP_USER and settings.SMTP_PASSWORD:
                    server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                    
                server.sendmail(settings.SMTP_FROM_EMAIL, to_email, msg.as_string())
            logger.info(f"Successfully sent SMTP email to {to_email}")
        except Exception as e:
            logger.error(f"Failed to send SMTP email to {to_email}: {str(e)}")
            raise ValueError(f"Email delivery failed: {str(e)}")
