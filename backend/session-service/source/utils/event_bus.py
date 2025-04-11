# source/utils/event_bus.py
import asyncio
import logging
from typing import Dict, List, Callable, Awaitable

logger = logging.getLogger('event_bus')

EventHandler = Callable[..., Awaitable[None]]


class EventBus:
    """Central event bus for application-wide communication"""

    def __init__(self):
        self.subscribers: Dict[str, List[EventHandler]] = {}
        logger.info("Event bus initialized")

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Subscribe to an event type with a handler function"""
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(handler)
        logger.debug(f"Subscribed to event: {event_type}")

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Unsubscribe a handler from an event type"""
        if event_type in self.subscribers and handler in self.subscribers[event_type]:
            self.subscribers[event_type].remove(handler)
            logger.debug(f"Unsubscribed from event: {event_type}")

    async def publish(self, event_type: str, **data) -> None:
        """Publish an event to all subscribers"""
        if event_type not in self.subscribers:
            return

        handlers = self.subscribers[event_type]

        if handlers:
            logger.debug(f"Publishing event {event_type} to {len(handlers)} subscribers")

            # Create tasks for all handlers
            tasks = [asyncio.create_task(handler(**data)) for handler in handlers]

            # Wait for all handlers to complete
            if tasks:
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Log any exceptions
                for i, result in enumerate(results):
                    if isinstance(result, Exception):
                        logger.error(f"Error in event handler for {event_type}: {result}")
        else:
            logger.debug(f"Event {event_type} published but no subscribers")


# Global event bus instance
event_bus = EventBus()
