"""API Routes Package"""

from .sector_rotation import router as sector_rotation_router
from .spot_rotation import router as spot_rotation_router

__all__ = ['sector_rotation_router', 'spot_rotation_router']
