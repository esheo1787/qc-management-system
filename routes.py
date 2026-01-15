"""
FastAPI API Routes - Backward Compatibility Layer.

This module re-exports the router and TAGS_METADATA from the new api/ package
for backward compatibility with existing imports.

New code should import directly from the api package:
    from api import router, TAGS_METADATA

This file will be kept for backward compatibility but the actual implementation
is now in the api/ package.
"""

# Re-export from the new api package for backward compatibility
from api import router, TAGS_METADATA

__all__ = ["router", "TAGS_METADATA"]
