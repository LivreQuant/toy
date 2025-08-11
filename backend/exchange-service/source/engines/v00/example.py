# source/conviction_engine/alpha_engines/target_weight/example_usage.py
from decimal import Decimal
from .engine import TargetWeightEngine
from .alpha_processor import TargetWeightSignal


def example_configurable_usage():
    """Example showing configuration-driven usage"""

    # Method 1: Use default configuration
    engine = TargetWeightEngine()

    # Method 2: Use custom configuration file
    # engine = TargetWeightEngine(config_path="/path/to/custom_params.yaml")

    # Method 3: Use configuration overrides
    config_overrides = {
        'constraint_manager.operational.aum': 500000000,  # $500M instead of default $100M
        'constraint_manager.operational.max_position_size': 0.05,  # 5% instead of 10%
        'risk_manager.firm_risk.max_single_position': 0.03,  # 3% firm limit
        'order_generator.execution.min_trade_size': 50000,  # $50K minimum trades
        'attribution.enable_performance_attribution': True,
        'logging.level': 'DEBUG'
    }

    engine_with_overrides = TargetWeightEngine(config_overrides=config_overrides)

    # Create signals
    signals = [
        TargetWeightSignal('AAPL', 0.08, 'HIGH'),
        TargetWeightSignal('GOOGL', 0.06, 'MEDIUM'),
        TargetWeightSignal('MSFT', 0.05, 'LOW'),
        TargetWeightSignal('TSLA', -0.03, 'HIGH'),
    ]

    current_portfolio = {
        'AAPL': 0.04,
        'MSFT': 0.02,
        'NVDA': 0.01  # Will be reduced to zero
    }

    market_data = {
        'AAPL': {
            'sector': 'Technology',
            'country': 'US',
            'market_cap': 3000000000000,
            'avg_daily_volume_usd': 50000000000,
            'volatility': 0.25
        },
        'GOOGL': {
            'sector': 'Technology',
            'country': 'US',
            'market_cap': 2000000000000,
            'avg_daily_volume_usd': 30000000000,
            'volatility': 0.22
        },
        'MSFT': {
            'sector': 'Technology',
            'country': 'US',
            'market_cap': 2800000000000,
            'avg_daily_volume_usd': 40000000000,
            'volatility': 0.20
        },
        'TSLA': {
            'sector': 'Consumer Discretionary',
            'country': 'US',
            'market_cap': 800000000000,
            'avg_daily_volume_usd': 25000000000,
            'volatility': 0.40
        },
        'NVDA': {
            'sector': 'Technology',
            'country': 'US',
            'market_cap': 1500000000000,
            'avg_daily_volume_usd': 35000000000,
            'volatility': 0.35
        }
    }

    # Process signals with the configurable engine
    result = engine_with_overrides.process_signal(
        signals=signals,
        current_portfolio=current_portfolio,
        market_data=market_data
    )

    print("=== CONFIGURATION-DRIVEN ENGINE RESULTS ===")
    print(f"\nEngine: {result['engine_version']}")
    print(f"Processing Time: {result['processing_time_ms']:.1f}ms")

    print(f"\nConfiguration Summary:")
    config_summary = result['config_used']
    for key, value in config_summary.items():
        print(f"  {key}: {value}")

    print(f"\nFinal Portfolio:")
    for symbol, weight in result['final_target_portfolio'].items():
        print(f"  {symbol}: {weight:.2%}")

    print(f"\nOrders ({len(result['orders'])}):")
    for order in result['orders']:
        print(f"  {order['side']} {order['symbol']}: ${order['delta_notional']:,.0f} "
              f"(urgency: {order['urgency']}, participation: {order['participation_rate']:.1%})")

    print(f"\nAttribution:")
    if result['attribution']:
        for key, value in result['attribution'].items():
            print(f"  {key}: {value}")

    print(f"\nConstraint Logs:")
    all_logs = (result['logs']['alpha_processing'] +
                result['logs']['constraints'] +
                result['logs']['risk_management'] +
                result['logs']['solver'])

    for log_entry in all_logs:
        if log_entry.get('type') == 'error':
            print(f"  ERROR: {log_entry}")
        elif log_entry.get('constraint'):
            print(f"  CONSTRAINT: {log_entry['constraint']} on {log_entry.get('symbol', 'portfolio')}")


def example_third_party_testing():
    """Example of third party testing with different configurations"""

    # Original strategy configuration
    original_config_overrides = {
        'constraint_manager.operational.aum': 100000000,  # $100M
        'constraint_manager.operational.max_position_size': 0.10,  # 10%
        'risk_manager.firm_risk.max_single_position': 0.05,  # 5%
    }

    # Third party configuration (larger, more conservative)
    third_party_config_overrides = {
        'constraint_manager.operational.aum': 1000000000,  # $1B
        'constraint_manager.operational.max_position_size': 0.03,  # 3%
        'risk_manager.firm_risk.max_single_position': 0.02,  # 2%
        'order_generator.urgency_parameters.HIGH.participation_rate': 0.10,  # More conservative
        'risk_manager.sector_limits.enable': True,  # Enable sector limits
        'risk_manager.sector_limits.technology': 0.25,  # Max 25% tech
    }

    # Same alpha signals
    signals = [
        TargetWeightSignal('AAPL', 0.15, 'HIGH'),
        TargetWeightSignal('GOOGL', 0.12, 'HIGH'),
        TargetWeightSignal('MSFT', 0.10, 'HIGH'),
    ]

    current_portfolio = {}

    market_data = {
        'AAPL': {'sector': 'Technology', 'country': 'US'},
        'GOOGL': {'sector': 'Technology', 'country': 'US'},
        'MSFT': {'sector': 'Technology', 'country': 'US'},
    }

    # Test with original configuration
    original_engine = TargetWeightEngine(config_overrides=original_config_overrides)
    original_result = original_engine.process_signal(signals, current_portfolio, market_data)

    # Test with third party configuration
    third_party_engine = TargetWeightEngine(config_overrides=third_party_config_overrides)
    third_party_result = third_party_engine.process_signal(signals, current_portfolio, market_data)

    print("=== CONFIGURATION COMPARISON ===")
    print(f"\nOriginal Strategy Results:")
    print(f"  Implementation Efficiency: {original_result['attribution'].get('implementation_efficiency', 'N/A'):.1%}")
    print(f"  Total Constraint Impact: {original_result['attribution'].get('total_constraint_impact', 0):.3f}")

    print(f"\nThird Party Strategy Results:")
    print(
        f"  Implementation Efficiency: {third_party_result['attribution'].get('implementation_efficiency', 'N/A'):.1%}")
    print(f"  Total Constraint Impact: {third_party_result['attribution'].get('total_constraint_impact', 0):.3f}")

    print(f"\nConstraint Differences:")
    orig_constraints = set(log.get('constraint', '') for log in
                           original_result['logs']['constraints'] + original_result['logs']['risk_management'])
    third_constraints = set(log.get('constraint', '') for log in
                            third_party_result['logs']['constraints'] + third_party_result['logs']['risk_management'])

    unique_to_third_party = third_constraints - orig_constraints
    if unique_to_third_party:
        print(f"  Additional constraints in third party: {unique_to_third_party}")


if __name__ == "__main__":
    example_configurable_usage()
    print("\n" + "=" * 60 + "\n")
    example_third_party_testing()