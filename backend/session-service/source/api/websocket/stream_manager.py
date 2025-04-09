# websocket/stream_manager.py
"""
Manages background asynchronous tasks (streams) associated with WebSocket sessions.
"""

import asyncio
import logging
from typing import Dict

logger = logging.getLogger('websocket_stream_manager')


class StreamManager:
    """Handles registration and cancellation of session-specific background tasks."""

    def __init__(self):
        """Initialize the StreamManager."""
        # session_id -> asyncio Task mapping
        self._streams: Dict[str, asyncio.Task] = {}
        logger.info("StreamManager initialized.")

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
            # Note: We don't await the old task here, just cancel and replace.
            # Consider if awaiting is needed depending on task cleanup requirements.

        self._streams[session_id] = task

        # Optional: Add a done callback to automatically remove finished/cancelled tasks
        task.add_done_callback(lambda t: self._handle_task_completion(session_id, t))

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
            except asyncio.CancelledError:
                logger.info(f"Stream task for session {session_id} successfully cancelled.")
            except asyncio.TimeoutError:
                logger.warning(f"Timeout waiting for stream task cancellation for session {session_id}.")
            except Exception as e:
                # Log any other errors during cancellation/awaiting
                logger.error(f"Error awaiting cancelled stream task for session {session_id}: {e}",
                             exc_info=False)  # Keep log concise
        elif task and task.done():
            logger.debug(f"Stream task for session {session_id} was already done when stop was called.")
        # else: No task found for session_id

    async def stop_all_streams(self):
        """Stop all managed stream tasks. Typically used during shutdown."""
        logger.info(f"Stopping all managed streams ({len(self._streams)})...")
        # Create a list of sessions to avoid issues if dict changes during iteration
        all_session_ids = list(self._streams.keys())
        tasks_to_await = []
        for session_id in all_session_ids:
            task = self._streams.pop(session_id, None)  # Use pop to clear dict as we go
            if task and not task.done():
                logger.debug(f"Cancelling stream during stop_all for session {session_id}")
                task.cancel()
                tasks_to_await.append(task)

        if tasks_to_await:
            # Wait for all cancellations using asyncio.gather
            # return_exceptions=True ensures one failed cancellation doesn't stop others
            results = await asyncio.gather(*tasks_to_await, return_exceptions=True)
            for i, result in enumerate(results):
                # Log any unexpected errors during the cancellation process
                if isinstance(result, Exception) and not isinstance(result, asyncio.CancelledError):
                    original_task_name = tasks_to_await[i].get_name()
                    logger.error(f"Error stopping stream task {original_task_name} during stop_all: {result}")
        logger.info("Finished stopping all streams.")

    def is_managing_stream(self, session_id: str) -> bool:
        """Check if a stream task is currently managed for the session."""
        return session_id in self._streams

    def _handle_task_completion(self, session_id: str, task: asyncio.Task):
        """Internal callback for when a managed task finishes (completes, cancels, or errors)."""
        # Remove the task from tracking if it's still the one registered
        # (handles race conditions if a new task was registered quickly)
        registered_task = self._streams.get(session_id)
        if registered_task is task:
            logger.debug(
                f"Stream task completed or cancelled for session {session_id}. Removing from active streams. Task: {task.get_name()}")
            del self._streams[session_id]
        # else: A new task was registered for this session before the old one's callback fired.

        # Log errors if the task completed with an exception
        try:
            exception = task.exception()
            if exception:
                logger.error(f"Managed stream task for session {session_id} finished with error: {exception}",
                             exc_info=exception)
        except asyncio.CancelledError:
            logger.debug(f"Managed stream task for session {session_id} was cancelled.")
        except asyncio.InvalidStateError:
            # Raised if exception() is called before the task is done (shouldn't happen in done_callback)
            logger.warning(f"InvalidStateError checking exception for task {task.get_name()}")
