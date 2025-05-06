import logging
from typing import Dict, Any, List, Optional

logger = logging.getLogger('validation')


class ValidationError(Exception):
    """Exception for validation errors"""

    def __init__(self, message: str, field: Optional[str] = None, details: Optional[Dict[str, Any]] = None):
        self.message = message
        self.field = field
        self.details = details or {}
        super().__init__(message)


def validate_required_fields(data: Dict[str, Any], required_fields: List[str]) -> None:
    """
    Validate that all required fields are present in the data
    
    Args:
        data: Data dictionary to validate
        required_fields: List of required field names
        
    Raises:
        ValidationError: If a required field is missing
    """
    missing_fields = [field for field in required_fields if field not in data]
    if missing_fields:
        raise ValidationError(f"Missing required fields: {', '.join(missing_fields)}")


def validate_numeric_field(data: Dict[str, Any], field: str, min_value: Optional[float] = None,
                           max_value: Optional[float] = None) -> None:
    """
    Validate that a field is numeric and within allowed range
    
    Args:
        data: Data dictionary to validate
        field: Field name to validate
        min_value: Minimum allowed value (inclusive)
        max_value: Maximum allowed value (inclusive)
        
    Raises:
        ValidationError: If field is not numeric or outside allowed range
    """
    if field not in data:
        return

    try:
        value = float(data[field])
        data[field] = value  # Convert to float if it's a string number
    except (ValueError, TypeError):
        raise ValidationError(f"Field '{field}' must be numeric", field=field)

    if min_value is not None and value < min_value:
        raise ValidationError(f"Field '{field}' must be greater than or equal to {min_value}", field=field)

    if max_value is not None and value > max_value:
        raise ValidationError(f"Field '{field}' must be less than or equal to {max_value}", field=field)


def validate_enum_field(data: Dict[str, Any], field: str, enum_class: Any) -> None:
    """
    Validate that a field contains a valid enum value
    
    Args:
        data: Data dictionary to validate
        field: Field name to validate
        enum_class: Enum class to check against
        
    Raises:
        ValidationError: If field value is not a valid enum value
    """
    if field not in data:
        return

    value = data[field]
    valid_values = [e.value for e in enum_class]

    if value not in valid_values:
        raise ValidationError(
            f"Field '{field}' must be one of: {', '.join(valid_values)}",
            field=field
        )
