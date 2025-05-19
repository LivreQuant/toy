# source/utils/property_mappings.py
from typing import Dict, Tuple, Any, Optional

# Team member property mapping
# Format: {'input_category': {'input_field': ('category', 'subcategory')}}
TEAM_MEMBER_MAPPING = {
    'personal': {
        'order': {'personal', 'id'},
        'firstName': ('personal', 'first_name'),
        'lastName': ('personal', 'last_name'),
        'birthDate': ('personal', 'birth_date')
    },
    'professional': {
        'role': ('employment', 'position'),
        'investmentExpertise': ('employment', 'expertise'),
        'yearsExperience': ('employment', 'years_experience'),
        'currentEmployment': ('employment', 'current_company'),
    },
    'social': {
        'linkedin': ('social', 'linkedin_url')
    },
    'education': {
        'institution': ('education')
    }
}

# Fund property mapping
# Format: 'input_field': ('category', 'subcategory')
FUND_MAPPING = {
    'location': ('location', 'state_country'),

    'legalStructure': ('property', 'legal_structure'),

    'yearEstablished': ('metadata', 'year_established'),
    'aumRange': ('metadata', 'aum_range'),
    'profilePurpose': ('metadata', 'objective'),
    'otherPurposeDetails': ('metadata', 'description'),
    'investmentStrategy': ('metadata', 'approach'),
}

# Book property mapping
# Format: 'input_field': ('category', 'subcategory')
BOOK_MAPPING = {
    'riskLevel': ('risk', 'level'),
    'maxDrawdown': ('risk', 'drawdown'),
    'volatility': ('risk', 'volatility'),
    'targetReturns': ('strategy', 'returns'),
    'benchmark': ('strategy', 'benchmark'),
    'horizon': ('strategy', 'timeframe'),
    'description': ('general', 'description'),
    'objective': ('general', 'objective'),
    'constraints': ('constraints', 'rules')
}

# Reverse mappings
def build_reverse_mapping(mapping: Dict) -> Dict:
    """Build reverse mapping from property mappings"""
    reversed_mapping = {}
    
    # For team member mapping
    if isinstance(next(iter(mapping.values()), {}), dict):
        for category, fields in mapping.items():
            for field, db_mapping in fields.items():
                reversed_mapping[db_mapping] = (category, field)
    # For fund mapping
    else:
        for field, db_mapping in mapping.items():
            reversed_mapping[db_mapping] = field
            
    return reversed_mapping

# Generate reverse mappings
REVERSE_TEAM_MEMBER_MAPPING = build_reverse_mapping(TEAM_MEMBER_MAPPING)
REVERSE_FUND_MAPPING = build_reverse_mapping(FUND_MAPPING)

def get_team_member_db_mapping(category: str, field: str, member_index: int = 0) -> Tuple[str, str, str]:
    """Get database mapping for a team member property, including order index"""
    if category in TEAM_MEMBER_MAPPING and field in TEAM_MEMBER_MAPPING[category]:
        base_category, subcategory = TEAM_MEMBER_MAPPING[category][field]
        # Add the index to make them unique per team member
        return (f"{base_category}_{member_index+1}", subcategory)
    return None

def get_original_team_member_field(db_category: str, db_subcategory: str) -> Tuple[Optional[str], Optional[str]]:
    """Get original field name from database mapping"""
    # Special handling for education - directly map without needing index
    if db_category == 'education' and db_subcategory == 'institutions':
        return ('education', 'institution')
    
    # Check if this is one of our mapped categories/subcategories
    for (mapped_cat, mapped_subcat), (orig_cat, orig_field) in REVERSE_TEAM_MEMBER_MAPPING.items():
        if db_category == mapped_cat and db_subcategory == mapped_subcat:
            return (orig_cat, orig_field)
        
    # No mapping found
    return (None, None)

def get_fund_db_mapping(field: str) -> Tuple[str, str, str]:
    """Get database mapping for a fund property"""
    return FUND_MAPPING.get(field, None)

def get_original_fund_field(db_category: str, db_subcategory: str) -> str:
    """Get original field name from database mapping"""
    db_mapping = (db_category, db_subcategory)
    return REVERSE_FUND_MAPPING.get(db_mapping, None)


# Add functions for book mappings
def get_book_db_mapping(field: str) -> Optional[Tuple[str, str, str]]:
    """Get database mapping for a book property"""
    return BOOK_MAPPING.get(field, None)

# Build reverse book mapping
REVERSE_BOOK_MAPPING = {db_mapping: field for field, db_mapping in BOOK_MAPPING.items()}

def get_original_book_field(db_category: str, db_subcategory: str) -> Optional[str]:
    """Get original field name from database mapping"""
    db_mapping = (db_category, db_subcategory)
    return REVERSE_BOOK_MAPPING.get(db_mapping, None)