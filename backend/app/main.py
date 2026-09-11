from fastapi import FastAPI
from app.routes.meta_auth import router as meta_auth_router


app = FastAPI(
    title="Social Media Agent API",
    version="1.0.0"
)


app.include_router(meta_auth_router)


@app.get("/")
async def root():
    return {
        "message": "Social Media Agent API is running"
    }


@app.get("/health")
async def health_check():
    return {
        "status": "healthy"
    }

from fastapi.responses import HTMLResponse

@app.get("/privacy-policy", response_class=HTMLResponse)
async def privacy_policy():
    return """
    <html>
        <body>
            <h1>Privacy Policy</h1>
            <p>This app does not store or share your personal data.</p>
        </body>
    </html>
    """
