# utils/retry.py
import random
import asyncio


async def retry_with_backoff(
    func,
    max_attempts=5,
    base_delay=1,
    max_delay=30,
    retriable_exceptions=(Exception,)
):
    """Generic retry mechanism with exponential backoff"""
    for attempt in range(max_attempts):
        try:
            return await func()
        except retriable_exceptions as e:
            if attempt == max_attempts - 1:
                raise
            delay = min(base_delay * (2 ** attempt) + random.uniform(0, 1), max_delay)
            await asyncio.sleep(delay)
