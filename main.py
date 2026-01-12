"""
FastAPI Main Application.
Sync mode for simplicity and SQLite compatibility.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from database import init_db
from routes import router

app = FastAPI(
    title="QC Management System",
    description="Internal QC/Work Management Tool",
    version="1.0.0",
)

# CORS (allow Streamlit dashboard)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routes
app.include_router(router)


@app.on_event("startup")
def on_startup():
    """Initialize database on startup."""
    init_db()


@app.get("/")
def root():
    """Health check."""
    return {"status": "ok", "service": "qc-management-system"}


@app.get("/health")
def health():
    """Health check endpoint."""
    return {"status": "healthy"}
