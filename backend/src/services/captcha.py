import uuid
import random
import httpx
import base64
from xml.sax.saxutils import escape
from src.config import settings
import src.core.redis as redis_module
from fastapi import HTTPException, status

class CaptchaService:
    def __init__(self):
        pass
    
    def _generate_svg(self, text: str) -> str:
        """Generates a simple, noisy SVG captcha."""
        width = 120
        height = 40
        svg_parts = [f'<svg width="{width}" height="{height}" xmlns="http://www.w3.org/2000/svg">']
        svg_parts.append('<rect width="100%" height="100%" fill="#f3f4f6" />')
        
        # Add noise lines
        for _ in range(5):
            x1 = random.randint(0, width)
            y1 = random.randint(0, height)
            x2 = random.randint(0, width)
            y2 = random.randint(0, height)
            svg_parts.append(f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="#9ca3af" stroke-width="2" />')
            
        # Add text
        colors = ["#4c1d95", "#8b5cf6", "#d946ef", "#be185d"]
        for i, char in enumerate(text):
            x = 10 + i * 20 + random.randint(-2, 2)
            y = 28 + random.randint(-4, 4)
            rotate = random.randint(-15, 15)
            color = random.choice(colors)
            escaped = escape(char)
            svg_parts.append(f'<text x="{x}" y="{y}" transform="rotate({rotate} {x} {y})" font-family="monospace" font-size="24" font-weight="bold" fill="{color}">{escaped}</text>')
            
        svg_parts.append('</svg>')
        svg_data = "".join(svg_parts)
        b64 = base64.b64encode(svg_data.encode('utf-8')).decode('utf-8')
        return f"data:image/svg+xml;base64,{b64}"

    async def generate_custom_captcha(self) -> dict:
        """Generates a custom SVG captcha and stores the answer in Redis."""
        chars = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
        text = "".join(random.choice(chars) for _ in range(5))
        svg_b64 = self._generate_svg(text)
        
        captcha_id = str(uuid.uuid4())
        # Store answer with 5 min TTL
        client = await redis_module.init_redis()
        if client:
            await client.set(f"captcha:{captcha_id}", text, ex=300)
            
        return {"captcha_id": captcha_id, "image_data": svg_b64}

    async def verify_captcha(self, captcha_token: str | None, captcha_id: str | None = None, ip_address: str | None = None) -> bool:
        """Verifies the CAPTCHA based on the active CAPTCHA_TYPE."""
        if settings.CAPTCHA_TYPE == "none":
            return True
            
        if not captcha_token:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Captcha token is required")

        if settings.CAPTCHA_TYPE == "custom":
            if not captcha_id:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Captcha ID is required for custom captcha")
            
            client = await redis_module.init_redis()
            if not client:
                raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Captcha service unavailable")
                
            expected = await client.get(f"captcha:{captcha_id}")
            if not expected:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Captcha expired or invalid ID")
                
            # Verify and delete to prevent reuse
            await client.delete(f"captcha:{captcha_id}")
            
            if captcha_token.upper().strip() != expected.upper():
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid captcha")
            return True
            
        elif settings.CAPTCHA_TYPE == "google":
            if not settings.GOOGLE_RECAPTCHA_SECRET:
                return True # Skip if not configured
                
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.post("https://www.google.com/recaptcha/api/siteverify", data={
                    "secret": settings.GOOGLE_RECAPTCHA_SECRET,
                    "response": captcha_token,
                    "remoteip": ip_address
                })
                data = resp.json()
                if not data.get("success"):
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Google reCAPTCHA")
                    
                score = data.get("score")
                if score is not None and score < 0.5:
                    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="reCAPTCHA score too low")
            return True
            
        return True
