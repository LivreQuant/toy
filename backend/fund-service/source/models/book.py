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
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert book to dictionary for serialization"""
        return {
            "book_id": self.book_id,
            "user_id": self.user_id,
            "name": self.name,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Book':
        """Create book from dictionary"""
        # Extract only the fields needed for the Book class
        book_data = {
            "book_id": data.get("book_id"),
            "user_id": data.get("user_id"),
            "name": data.get("name"),
            "status": data.get("status", "active")
        }
        return cls(**book_data)


@dataclass
class BookProperty:
    """Property model for book properties using EAV pattern"""
    book_id: str
    category: str
    key: str
    value: str
    subcategory: str = ""
    property_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    active_at: float = field(default_factory=time.time)
    expite_at: float = field(default_factory=time.time)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert property to dictionary for serialization"""
        return {
            "property_id": self.property_id,
            "book_id": self.book_id,
            "category": self.category,
            "subcategory": self.subcategory,
            "key": self.key,
            "value": self.value,
            "active_at": self.active_at,
            "expite_at": self.expite_at
        }