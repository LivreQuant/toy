# source/models/book.py
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
    status: str = "active"
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert book to dictionary for serialization"""
        return {
            "book_id": self.book_id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Book':
        """Create book from dictionary"""
        return cls(**data)


@dataclass
class BookProperty:
    """Property model for book properties using EAV pattern"""
    book_id: str
    category: str
    key: str
    value: str
    subcategory: str = ""
    property_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert property to dictionary for serialization"""
        return {
            "property_id": self.property_id,
            "book_id": self.book_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "key": self.key,
            "value": self.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at
        }