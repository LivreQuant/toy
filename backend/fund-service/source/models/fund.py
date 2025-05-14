from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import time
import uuid
import json


@dataclass
class Fund:
    """Fund model representing an investment fund entity"""
    user_id: str
    name: str
    status: str = "active"  # active, archived, pending
    fund_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert fund to dictionary for serialization"""
        return {
            "fund_id": self.fund_id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_json(self) -> str:
        """Convert fund to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Fund':
        """Create fund from dictionary"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Fund':
        """Create fund from JSON string"""
        return cls.from_json(json.loads(json_str))


@dataclass
class FundProperty:
    """Property model for flexible fund properties using EAV pattern"""
    fund_id: str
    category: str    # 'general', 'strategy', 'team', 'compliance'
    subcategory: str # 'legalStructure', 'investmentThesis', 'teamMemberRole'
    key: str         # For array items like 'objective[0]', 'objective[1]'
    value: str
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert property to dictionary for serialization"""
        return {
            "fund_id": self.fund_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }