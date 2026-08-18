"""Entry point for the full Local Hub operational API deployment.

The Vercel ``server.py`` entry point intentionally exposes only the restricted
cloud gateway. Operational hosting platforms must import this module instead
so authentication, Retail, Cafe, billing, reporting, and governance routes are
available under the Local Hub deployment profile.
"""

from app.main import app

__all__ = ["app"]
