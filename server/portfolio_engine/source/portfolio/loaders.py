#!/usr/bin/env python3
"""
Corporate actions data loaders
"""

import pandas as pd
import os
from typing import List, Dict
from decimal import Decimal
from .models import (SymbolChange, Delisting, Merger, MergerComponent, 
                     StockSplit, StockDividend, CashDividend, CorporateAction)
from .config import config
import logging

logger = logging.getLogger(__name__)

class CorporateActionsLoader:
    """Loads unified and manual corporate actions data"""
    
    def __init__(self):
        self.unified_actions: List[CorporateAction] = []
        self.manual_actions: List[CorporateAction] = []
    
    def load_all(self) -> List[CorporateAction]:
        """Load all corporate actions (unified + manual)"""
        self.load_unified_actions()
        self.load_manual_actions()
        
        # Combine and deduplicate (manual overrides unified)
        manual_symbols = {(action.symbol, action.action_type) for action in self.manual_actions}
        unified_filtered = [action for action in self.unified_actions 
                          if (action.symbol, action.action_type) not in manual_symbols]
        
        return self.manual_actions + unified_filtered
    
    def load_unified_actions(self):
        """Load unified corporate actions from CSV files"""
        logger.info("Loading unified corporate actions...")
        
        # Symbol changes
        self._load_unified_symbol_changes()
        
        # Delistings
        self._load_unified_delistings()
        
        # Mergers
        self._load_unified_mergers()
        
        # Stock splits
        self._load_unified_stock_splits()
        
        # Stock dividends
        self._load_unified_stock_dividends()
        
        # Cash dividends
        self._load_unified_cash_dividends()
        
        logger.info(f"Loaded {len(self.unified_actions)} unified corporate actions")
    
    def _load_unified_symbol_changes(self):
        """Load unified symbol changes"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_symbol_changes.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = SymbolChange(
                    symbol=row['old_symbol'],
                    action_type='SYMBOL_CHANGE',
                    effective_date=row['change_date'],
                    source=f"unified_{row['source']}",
                    old_symbol=row['old_symbol'],
                    new_symbol=row['new_symbol']
                )
                self.unified_actions.append(action)
    
    def _load_unified_delistings(self):
        """Load unified delistings"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_delisting.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = Delisting(
                    symbol=row['master_symbol'],
                    action_type='DELISTING',
                    effective_date=row.get('delisting_date', ''),
                    source=f"unified_{row['source']}",
                    currency='USD',
                    account='Credit',
                    value_per_share=Decimal('0')  # needs manual override
                )
                self.unified_actions.append(action)
    
    def _load_unified_mergers(self):
        """Load unified mergers"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_mergers.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                components = []  # needs manual override for actual payout
                action = Merger(
                    symbol=row['acquiree_symbol'],
                    action_type='MERGER',
                    effective_date=row.get('ex_date', ''),
                    source=f"unified_{row['source']}",
                    components=components
                )
                self.unified_actions.append(action)
    
    def _load_unified_stock_splits(self):
        """Load unified stock splits"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_stock_splits.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                # Calculate split ratio from numerator/denominator
                numerator = row.get('numerator', 1)
                denominator = row.get('denominator', 1)
                split_ratio = Decimal(str(numerator)) / Decimal(str(denominator))
                
                action = StockSplit(
                    symbol=row['master_symbol'],
                    action_type='STOCK_SPLIT',
                    effective_date=row.get('ex_date', ''),
                    source=f"unified_{row['source']}",
                    split_ratio=split_ratio
                )
                self.unified_actions.append(action)
    
    def _load_unified_stock_dividends(self):
        """Load unified stock dividends"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_stock_dividends.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                dividend_ratio = Decimal(str(row.get('dividend_ratio', 0)))
                
                action = StockDividend(
                    symbol=row['master_symbol'],
                    action_type='STOCK_DIVIDEND',
                    effective_date=row.get('ex_date', ''),
                    source=f"unified_{row['source']}",
                    dividend_ratio=dividend_ratio
                )
                self.unified_actions.append(action)
    
    def _load_unified_cash_dividends(self):
        """Load unified cash dividends"""
        file_path = os.path.join(config.CA_DATA_DIR, "unified_cash_dividends.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                dividend_amount = Decimal(str(row.get('dividend_amount', 0)))
                
                action = CashDividend(
                    symbol=row['master_symbol'],
                    action_type='CASH_DIVIDEND',
                    effective_date=row.get('ex_date', ''),
                    source=f"unified_{row['source']}",
                    dividend_per_share=dividend_amount,
                    currency=row.get('currency', 'USD'),
                    account='Credit'
                )
                self.unified_actions.append(action)
    
    def load_manual_actions(self):
        """Load manual corporate action overrides"""
        logger.info("Loading manual corporate actions...")
        
        os.makedirs(config.MANUAL_CA_DIR, exist_ok=True)
        
        self._load_manual_symbol_changes()
        self._load_manual_delistings()
        self._load_manual_mergers()
        self._load_manual_stock_splits()
        self._load_manual_stock_dividends()
        self._load_manual_cash_dividends()
        
        logger.info(f"Loaded {len(self.manual_actions)} manual corporate actions")
    
    def _load_manual_symbol_changes(self):
        """Load manual symbol changes"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "symbol_changes.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = SymbolChange(
                    symbol=row['symbol'],
                    action_type='SYMBOL_CHANGE',
                    effective_date='manual',
                    source='manual',
                    old_symbol=row['symbol'],
                    new_symbol=row['new_symbol']
                )
                self.manual_actions.append(action)
    
    def _load_manual_delistings(self):
        """Load manual delistings"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "delistings.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = Delisting(
                    symbol=row['symbol'],
                    action_type='DELISTING',
                    effective_date='manual',
                    source='manual',
                    currency=row['currency'],
                    account=row['account'],
                    value_per_share=Decimal(str(row['value']))
                )
                self.manual_actions.append(action)
    
    def _load_manual_mergers(self):
        """Load manual mergers"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "mergers.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            merger_dict = {}
            
            for _, row in df.iterrows():
                symbol = row['symbol']
                if symbol not in merger_dict:
                    merger_dict[symbol] = []
                
                component = MergerComponent(
                    type=row['type'],
                    parent=row['parent'],
                    currency=row.get('currency') if pd.notna(row.get('currency')) else None,
                    value=Decimal(str(row['value']))
                )
                merger_dict[symbol].append(component)
            
            for symbol, components in merger_dict.items():
                action = Merger(
                    symbol=symbol,
                    action_type='MERGER',
                    effective_date='manual',
                    source='manual',
                    components=components
                )
                self.manual_actions.append(action)
    
    def _load_manual_stock_splits(self):
        """Load manual stock splits"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "stock_splits.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = StockSplit(
                    symbol=row['symbol'],
                    action_type='STOCK_SPLIT',
                    effective_date='manual',
                    source='manual',
                    split_ratio=Decimal(str(row['split_ratio']))
                )
                self.manual_actions.append(action)
    
    def _load_manual_stock_dividends(self):
        """Load manual stock dividends"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "stock_dividends.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = StockDividend(
                    symbol=row['symbol'],
                    action_type='STOCK_DIVIDEND',
                    effective_date='manual',
                    source='manual',
                    dividend_ratio=Decimal(str(row['dividend_ratio']))
                )
                self.manual_actions.append(action)
    
    def _load_manual_cash_dividends(self):
        """Load manual cash dividends"""
        file_path = os.path.join(config.MANUAL_CA_DIR, "cash_dividends.csv")
        if os.path.exists(file_path):
            df = pd.read_csv(file_path)
            for _, row in df.iterrows():
                action = CashDividend(
                    symbol=row['symbol'],
                    action_type='CASH_DIVIDEND',
                    effective_date='manual',
                    source='manual',
                    dividend_per_share=Decimal(str(row['dividend_per_share'])),
                    currency=row['currency'],
                    account=row['account']
                )
                self.manual_actions.append(action)
    
    def create_manual_templates(self):
        """Create template CSV files for manual corporate actions"""
        os.makedirs(config.MANUAL_CA_DIR, exist_ok=True)
        
        # Symbol changes
        if not os.path.exists(os.path.join(config.MANUAL_CA_DIR, "symbol_changes.csv")):
            pd.DataFrame({
                'symbol': ['GE'],
                'new_symbol': ['GEW']
            }).to_csv(os.path.join(config.MANUAL_CA_DIR, "symbol_changes.csv"), index=False)
        
        # Delistings
        if not os.path.exists(os.path.join(config.MANUAL_CA_DIR, "delistings.csv")):
            pd.DataFrame({
                'symbol': ['BBBY'],
                'currency': ['USD'],
                'account': ['Credit'],
                'value': [0.00]
            }).to_csv(os.path.join(config.MANUAL_CA_DIR, "delistings.csv"), index=False)
        
        # Mergers
        if not os.path.exists(os.path.join(config.MANUAL_CA_DIR, "mergers.csv")):
            pd.DataFrame({
                'symbol': ['GE', 'GE'],
                'type': ['stock', 'cash'],
                'parent': ['GEW', 'Credit'],
                'currency': [None, 'USD'],
                'value': [0.34, 10.0]
            }).to_csv(os.path.join(config.MANUAL_CA_DIR, "mergers.csv"), index=False)
        
        # Stock splits
        if not os.path.exists(os.path.join(config.MANUAL_CA_DIR, "stock_splits.csv")):
            pd.DataFrame({
                'symbol': ['AAPL'],
                'split_ratio': [2.0]  # 2:1 split
            }).to_csv(os.path.join(config.MANUAL_CA_DIR, "stock_splits.csv"), index=False)
        
        # Stock dividends
        if not os.path.exists(os.path.join(config.MANUAL_CA_DIR, "stock_dividends.csv")):
            pd.DataFrame({
                'symbol': ['MSFT'],
                'dividend_ratio': [0.05]  # 5% stock dividend
            }).to_csv(os.path.join(config.MANUAL_CA_DIR, "stock_dividends.csv"), index=False)
        
        # Cash dividends
        if not os.path.exists(os.path.join(config.MANUAL_CA_DIR, "cash_dividends.csv")):
            pd.DataFrame({
                'symbol': ['AAPL'],
                'dividend_per_share': [0.25],
                'currency': ['USD'],
                'account': ['Credit']
            }).to_csv(os.path.join(config.MANUAL_CA_DIR, "cash_dividends.csv"), index=False)
        
        logger.info(f"Created manual corporate actions templates in {config.MANUAL_CA_DIR}")