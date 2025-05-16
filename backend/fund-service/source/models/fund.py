# source/models/fund.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import uuid
import time  # Add this import
import json


@dataclass
class Fund:
    """Fund model representing an investment fund entity"""
    user_id: str
    name: str
    status: str = "active"  # active, archived, pending
    fund_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert fund to dictionary for serialization"""
        return {
            "fund_id": self.fund_id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status
        }
    
    def to_json(self) -> str:
        """Convert fund to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Fund':
        """Create fund from dictionary"""
        # Extract only the fields needed for the Fund class
        fund_data = {
            "fund_id": data.get("fund_id"),
            "user_id": data.get("user_id"),
            "name": data.get("name"),
            "status": data.get("status", "active")
        }
        return cls(**fund_data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Fund':
        """Create fund from JSON string"""
        return cls.from_dict(json.loads(json_str))

@dataclass
class FundProperty:
    """Property model for flexible fund properties using EAV pattern"""
    fund_id: str
    category: str    # 'general', 'strategy', 'team', 'compliance'
    subcategory: str # 'legalStructure', 'investmentThesis', 'teamMemberRole'
    key: str         # For array items like 'objective[0]', 'objective[1]'
    value: str
    active_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert property to dictionary for serialization"""
        return {
            "fund_id": self.fund_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "key": self.key,
            "value": self.value,
            "active_at": self.active_at,
            "updated_at": self.updated_at
        }