# utils/retry.py
import logging
import random
import asyncio

logger = logging.getLogger('retry_with_backoff_generator')


async def retry_with_backoff_generator(
    generator_func,
    max_attempts=5,
    base_delay=1,
    max_delay=30,
    retriable_exceptions=(Exception,)
):
    """
    Generic retry mechanism with exponential backoff for async generators.
    
    Args:
        generator_func: Function returning an async generator
        max_attempts: Maximum number of retry attempts
        base_delay: Base delay time (seconds)
        max_delay: Maximum delay time (seconds)
        retriable_exceptions: Tuple of exception types to retry on
        
    Yields:
        Items from the async generator
    """
    attempt = 0
    while attempt < max_attempts:
        try:
            # Create a new generator
            gen = generator_func()
            # Iterate through it
            async for item in gen:
                yield item
            # If we successfully iterate through the entire generator, we're done
            return
        except retriable_exceptions as e:
            attempt += 1
            if attempt >= max_attempts:
                raise
            
            # Exponential backoff with jitter
            delay = min(base_delay * (2 ** (attempt - 1)) + random.uniform(0, 1), max_delay)
            logger.warning(f"Retry attempt {attempt}/{max_attempts} after error: {e}. Waiting {delay:.2f}s")
            await asyncio.sleep(delay)
