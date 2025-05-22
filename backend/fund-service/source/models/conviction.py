# source/models/conviction.py
from dataclasses import dataclass, field
from typing import Optional, Dict, Any, Union
import uuid
import json

@dataclass
class ConvictionData:
    """Conviction data model matching frontend ConvictionData interface exactly"""
    
    # All fields are optional during processing, but some become required for API calls
    instrumentId: Optional[str] = None
    participationRate: Optional[Union[str, int, float]] = None  # 'LOW', 'MEDIUM', 'HIGH', or number
    tag: Optional[str] = None
    convictionId: Optional[str] = None
    
    # Optional depending on the conviction format
    side: Optional[str] = None  # 'BUY', 'SELL', 'CLOSE'
    score: Optional[float] = None
    quantity: Optional[float] = None
    zscore: Optional[float] = None
    targetPercent: Optional[float] = None
    targetNotional: Optional[float] = None
    
    # Allow dynamic properties for multi-horizon z-scores
    # [key: string]: string | number | undefined
    additional_properties: Dict[str, Union[str, int, float]] = field(default_factory=dict)

    def __post_init__(self):
        """Generate convictionId if not provided"""
        if not self.convictionId:
            self.convictionId = str(uuid.uuid4())

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary"""
        result = {
            "instrumentId": self.instrumentId,
            "participationRate": self.participationRate,
            "tag": self.tag,
            "convictionId": self.convictionId,
            "side": self.side,
            "score": self.score,
            "quantity": self.quantity,
            "zscore": self.zscore,
            "targetPercent": self.targetPercent,
            "targetNotional": self.targetNotional
        }
        
        # Add dynamic properties
        result.update(self.additional_properties)
        
        # Remove None values
        return {k: v for k, v in result.items() if v is not None}

    def to_json(self) -> str:
        """Convert to JSON string"""
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConvictionData':
        """Create from dictionary"""
        # Known fields
        known_fields = {
            'instrumentId', 'participationRate', 'tag', 'convictionId',
            'side', 'score', 'quantity', 'zscore', 'targetPercent', 'targetNotional'
        }
        
        # Extract known fields
        conviction_data = {}
        additional_properties = {}
        
        for key, value in data.items():
            if key in known_fields:
                conviction_data[key] = value
            else:
                additional_properties[key] = value
        
        conviction_data['additional_properties'] = additional_properties
        return cls(**conviction_data)

    @classmethod
    def from_json(cls, json_str: str) -> 'ConvictionData':
        """Create from JSON string"""
        return cls.from_dict(json.loads(json_str))