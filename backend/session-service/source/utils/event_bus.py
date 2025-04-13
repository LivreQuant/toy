# source/event_bus.py
import asyncio
from typing import Callable, Dict
from dataclasses import dataclass, field


@dataclass
class EventBus:
    """Simplified async event bus"""
    _subscribers: Dict[str, list[Callable]] = field(default_factory=dict)

    async def publish(self, event_type: str, **kwargs):
        """
        Publish an event to all subscribers

        Args:
            event_type: Type of event
            kwargs: Event payload
        """
        if event_type not in self._subscribers:
            return

        tasks = [
            asyncio.create_task(subscriber(**kwargs))
            for subscriber in self._subscribers[event_type]
        ]

        # Wait for all tasks, ignore individual task failures
        await asyncio.gather(*tasks, return_exceptions=True)

    def subscribe(self, event_type: str, subscriber: Callable):
        """
        Subscribe to an event type

        Args:
            event_type: Type of event
            subscriber: Async function to handle event
        """
        if event_type not in self._subscribers:
            self._subscribers[event_type] = []

        self._subscribers[event_type].append(subscriber)


# Global event bus
event_bus = EventBus()
