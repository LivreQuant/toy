async def start_session_tasks(self):
    """Start background cleanup task and simulator heartbeat task"""
    if self.cleanup_task is None or self.cleanup_task.done():
        self.cleanup_task = asyncio.create_task(self.tasks.run_cleanup_loop())
        logger.info("Started session cleanup task.")

    if self.heartbeat_task is None or self.heartbeat_task.done():
        self.heartbeat_task = asyncio.create_task(self.tasks.run_simulator_heartbeat_loop())
        logger.info("Started simulator heartbeat task.")


async def stop_cleanup_task(self):
    """Stop background cleanup task and heartbeat task"""
    logger.info("Stopping background tasks (cleanup, heartbeat)...")
    if self.cleanup_task and not self.cleanup_task.done():
        self.cleanup_task.cancel()
        try:
            await self.cleanup_task
        except asyncio.CancelledError:
            logger.info("Session cleanup task cancelled.")
        except Exception as e:
            logger.error(f"Error awaiting cancelled cleanup task: {e}")
        self.cleanup_task = None

    if self.heartbeat_task and not self.heartbeat_task.done():
        self.heartbeat_task.cancel()
        try:
            await self.heartbeat_task
        except asyncio.CancelledError:
            logger.info("Simulator heartbeat task cancelled.")
        except Exception as e:
            logger.error(f"Error awaiting cancelled heartbeat task: {e}")
        self.heartbeat_task = None
    logger.info("Background tasks stopped.")


async def validate_session(self, session_id, token, device_id=None):
    """Delegate to session operations"""
    return await self.session_ops.validate_session(session_id, token, device_id)
