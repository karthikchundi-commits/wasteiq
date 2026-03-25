from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import Base, engine
from app.api.routes import auth, projects, predictions, actuals, recommendations, oracle, procurement, analytics
from app.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on first startup — wrapped so a DB error doesn't
    # prevent the health endpoint from responding
    try:
        Base.metadata.create_all(bind=engine)
    except Exception as e:
        print(f"DB init warning: {e}")
    yield


app = FastAPI(title="WasteIQ API", version="1.0.0", lifespan=lifespan)

allowed_origins = [
    "http://localhost:3000",
    "https://localhost:3000",
    "https://wasteiqfrontend.vercel.app",
]
if settings.frontend_url:
    allowed_origins.append(settings.frontend_url)

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_origin_regex=r"https://.*\.vercel\.app",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(projects.router)
app.include_router(predictions.router)
app.include_router(actuals.router)
app.include_router(recommendations.router)
app.include_router(oracle.router)
app.include_router(procurement.router)
app.include_router(analytics.router)


@app.get("/health")
def health():
    return {"status": "ok", "service": "WasteIQ API"}
