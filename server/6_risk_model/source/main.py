# main.py
import logging
from datetime import date
from db.risk_manager import RiskManager
from db.symbol_manager import SymbolManager
from models.random import RandomRiskModel
from config import config


def setup_logging():
    """Setup logging based on config"""
    log_level = getattr(logging, config.log_level.upper(), logging.INFO)
    logging.basicConfig(
        level=log_level,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )


def main():
    """
    Main function to run the risk model generation and loading process.
    """
    setup_logging()

    today = date.today()
    model_name = "RANDOM"

    try:
        logging.info(
            f"Starting risk model generation and loading for {today} with model '{model_name}' in {config.environment} environment.")

        # Step 1: Load the universe of symbols
        symbol_manager = SymbolManager()

        if not symbols:
            logging.error("No symbols were retrieved. Aborting process.")
            return False

        # Step 2: Generate the risk model data
        risk_model = RandomRiskModel(model=model_name, symbol_manager=symbol_manager)
        risk_model.generate_exposures(date=today)

        # Step 3: Load the data into the database
        #risk_manager = RiskManager()
        #risk_manager.load(data)
        risk_model.save_file()

        logging.info("Risk model generation and loading process completed successfully.")
        return True

    except Exception as e:
        logging.error(f"An error occurred during the process: {e}")
        return False


if __name__ == "__main__":
    success = main()
    print(f"Process Status: {'Success' if success else 'Failure'}")
