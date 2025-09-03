#!/usr/bin/env python3
"""
Main entry point for portfolio corporate actions processing
"""

import sys
from datetime import datetime
import logging
from source.portfolio.engine import MultiUserPortfolioEngine
from source.config import config


def setup_logging():
    """Setup logging configuration"""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler('portfolio_engine.log')
        ]
    )


def main():
    """Main function"""
    # Setup logging
    setup_logging()
    logger = logging.getLogger(__name__)

    try:
        # Validate date format
        datetime.strptime(config.PROCESSING_YMD, '%Y%m%d')

        logger.info(f"Starting portfolio processing for date: {config.PROCESSING_YMD}")
        logger.info(f"SOD directory: {config.SOD_DIR}")
        logger.info(f"CA data directory: {config.CA_DATA_DIR}")

        # Initialize engine
        engine = MultiUserPortfolioEngine(current_ymd=config.PROCESSING_YMD)

        # Load corporate actions
        logger.info("Loading corporate actions...")
        corporate_actions = engine.load_corporate_actions()
        logger.info(f"Loaded {len(corporate_actions)} corporate actions")

        # Load user portfolios
        logger.info("Loading user portfolios...")
        user_portfolios = engine.load_users(config.SOD_DIR)
        logger.info(f"Loaded portfolios for {len(user_portfolios)} users")

        # Process all users
        logger.info("Processing corporate actions for all users...")
        user_updates = engine.process_all_users()

        # Save results
        logger.info("Saving results...")
        engine.save_results(config.SOD_DIR)

        # Print summary
        print("\n" + "=" * 80)
        print("PROCESSING SUMMARY")
        print("=" * 80)

        for user_id, user_update in user_updates.items():
            print(f"\nUser: {user_id}")
            print(f"  Original positions: {len(user_update.original_portfolio.positions)}")
            print(f"  Final positions: {len([q for q in user_update.final_positions.values() if q != 0])}")
            print(f"  Corporate actions applied: {len(user_update.updates)}")
            print(f"  Account balances:")
            for currency, balance in user_update.final_accounts.items():
                print(f"    {currency}: {balance}")

        print(f"\nResults saved to: {config.SOD_DIR}")
        logger.info("Portfolio processing completed successfully")

    except Exception as e:
        logger.error(f"Error during processing: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()
