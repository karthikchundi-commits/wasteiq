from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.api.routes import auth, projects, predictions, actuals
from app.config import settings

# Create all tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="WasteIQ API", version="1.0.0")

# Allow localhost for development + any Vercel preview/production URLs
allowed_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
]
if settings.frontend_url:
    allowed_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",  # covers all preview deployments
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(predictions.router)
app.include_router(actuals.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "WasteIQ API"}
