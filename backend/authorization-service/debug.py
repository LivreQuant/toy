import asyncio
import logging
import os
from dotenv import load_dotenv

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

# Load environment variables
load_dotenv()

from source.db.db_manager import DatabaseManager
from source.core.auth_manager import AuthManager


async def main():
    # Create database manager
    db_manager = DatabaseManager()

    try:
        # Connect to database
        await db_manager.connect()

        # Create auth manager
        auth_manager = AuthManager(db_manager)

        # Simulate some operations
        print("Testing login...")
        login_result = await auth_manager.login('testuser', 'password123')
        print("Login Result:", login_result)

        # Keep the script running to observe background tasks
        while True:
            await asyncio.sleep(3600)

    except Exception as e:
        logging.error(f"Debugging error: {e}", exc_info=True)
    finally:
        # Cleanup
        await db_manager.close()


if __name__ == '__main__':
    asyncio.run(main())