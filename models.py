from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List

@dataclass
class ContractorProfile:
    trade: str                         # e.g., "painting", "plumbing", "electrical", "handyman"
    company_name: str
    contact_name: str
    phone: str
    email: str
    hourly_rate: float                 # e.g., 85.0
    min_callout_fee: float             # e.g., 150.0
    service_radius_miles: int          # e.g., 30
    license_number: Optional[str] = None
    auto_pilot: bool = False           # If True, automatically submits bids without waiting for SMS
    target_city: str = "Austin"
    standard_rates: dict = field(default_factory=dict)  # item -> price

@dataclass
class JobLead:
    id: str
    title: str
    source: str
    url: str
    location: str
    description: str
    posted_at: Optional[datetime] = None
    detected_trade: Optional[str] = None
    extracted_budget: Optional[str] = None
    is_valid_lead: bool = True
    rejection_reason: Optional[str] = None
    suggested_bid_amount: Optional[float] = None
    bid_price_range: Optional[str] = None
    generated_proposal: Optional[str] = None
    status: str = "PENDING"             # PENDING, SUBMITTED, DECLINED, SKIPPED
