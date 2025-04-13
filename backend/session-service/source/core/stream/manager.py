# stream_manager.py
"""
Manages background asynchronous tasks (streams) associated with WebSocket sessions.
"""
import asyncio
import logging
from typing import Dict

from source.utils.event_bus import event_bus

logger = logging.getLogger('stream_manager')


class StreamManager:
    """Handles registration and cancellation of session-specific background tasks."""

    def __init__(self):
        """Initialize the StreamManager."""
        # session_id -> asyncio Task mapping
        self._streams: Dict[str, asyncio.Task] = {}

        logger.info("StreamManager initialized")

    def register_stream(self, session_id: str, task: asyncio.Task):
        """
        Register a new background task for a session.

        If a task already exists for this session, the old one will be
        cancelled before registering the new one.

        Args:
            session_id: The session ID the task is associated with.
            task: The asyncio.Task instance to manage.
        """
        if not isinstance(task, asyncio.Task):
            logger.error(f"Attempted to register non-Task object for session {session_id}")
            return  # Or raise TypeError

        logger.info(f"Registering stream task for session {session_id}. Task: {task.get_name()}")

        # Check if a stream already exists for this session
        existing_task = self._streams.get(session_id)
        if existing_task and not existing_task.done():
            logger.warning(f"Replacing existing stream task for session {session_id}. Cancelling old task.")
            existing_task.cancel()

        self._streams[session_id] = task

        # Optional: Add a done callback to automatically remove finished/cancelled tasks
        task.add_done_callback(lambda t: self._handle_task_completion(session_id, t))

        # Publish event that stream was started
        asyncio.create_task(event_bus.publish('stream_started', session_id=session_id))

    async def stop_stream(self, session_id: str):
        """
        Stop and remove the stream task for a given session ID, if it exists.

        Args:
            session_id: The session ID whose stream should be stopped.
        """
        task = self._streams.pop(session_id, None)
        if task and not task.done():
            logger.info(f"Stopping stream task for session {session_id}. Task: {task.get_name()}")
            task.cancel()
            try:
                # Wait briefly for cancellation to occur, but don't block indefinitely
                await asyncio.wait_for(task, timeout=1.0)
                logger.debug(f"Stream task for session {session_id} awaited after cancellation.")
                # Publish event that stream was stopped
                await event_bus.publish('stream_stopped', session_id=session_id)
            except asyncio.CancelledError:
                logger.info(f"Stream task for session {session_id} successfully cancelled.")
                await event_bus.publish('stream_stopped', session_id=session_id)
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for stream task cancellation for session {session_id}.")
            except Exception as e:
                # Log any other errors during cancellation/awaiting
                logger.error(f"Error awaiting cancelled stream task for session {session_id}: {e}",
                             exc_info=False)  # Keep log concise
        elif task and task.done():
            logger.debug(f"Stream task for session {session_id} was already done when stop was called.")
            await event_bus.publish('stream_stopped', session_id=session_id)

    def _handle_task_completion(self, session_id: str, task: asyncio.Task):
        """Internal callback for when a managed task finishes (completes, cancels, or errors)."""
        # Remove the task from tracking if it's still the one registered
        # (handles race conditions if a new task was registered quickly)
        registered_task = self._streams.get(session_id)
        if registered_task is task:
            logger.debug(
                f"Stream task completed or cancelled for session {session_id}. Removing from active streams. Task: {task.get_name()}")
            del self._streams[session_id]
            # Publish event that stream ended
            asyncio.create_task(event_bus.publish('stream_ended', session_id=session_id))

        # Log errors if the task completed with an exception
        try:
            exception = task.exception()
            if exception:
                logger.error(f"Managed stream task for session {session_id} finished with error: {exception}",
                             exc_info=exception)
                # Publish stream error event
                asyncio.create_task(event_bus.publish('stream_error',
                                                      session_id=session_id,
                                                      error=str(exception)))
        except asyncio.CancelledError:
            logger.debug(f"Managed stream task for session {session_id} was cancelled.")
        except asyncio.InvalidStateError:
            # Raised if exception() is called before the task is done (shouldn't happen in done_callback)
            logger.warning(f"InvalidStateError checking exception for task {task.get_name()}")
