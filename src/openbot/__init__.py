import asyncio
from .main import main as async_main

__all__ = ["main"]


def main():
    """Sync wrapper for async main function"""
    asyncio.run(async_main())
