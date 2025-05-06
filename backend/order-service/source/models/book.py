from dataclasses import dataclass, field
from typing import Optional, Dict, Any, List
import time
import uuid
import json


@dataclass
class Book:
    """Book model representing a trading configuration"""
    user_id: str
    name: str
    book_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    details: Optional[List[List]] = None  # New field for the details list
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert book to dictionary for serialization"""
        return {
            "book_id": self.book_id,
            "user_id": self.user_id,
            "name": self.name,
            "details": self.details,  # Include the details field
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    def to_json(self) -> str:
        """Convert book to JSON string"""
        return json.dumps(self.to_dict())
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Book':
        """Create book from dictionary"""
        return cls(**data)
    
    @classmethod
    def from_json(cls, json_str: str) -> 'Book':
        """Create book from JSON string"""
        return cls.from_dict(json.loads(json_str))