from pydantic import BaseModel
from typing import Optional


class SourceClaim(BaseModel):
    value: Optional[str] = None
    source: str
    confidence: str
    status: str
    notes: Optional[str] = None


class ProductExtraction(BaseModel):
    model: list[SourceClaim]
    rated_power: list[SourceClaim]
    manufacturer: list[SourceClaim]
    factory_address: list[SourceClaim]
    country_of_manufacture: list[SourceClaim]
    ip_rating: list[SourceClaim]
    weight: list[SourceClaim]
    max_efficiency: list[SourceClaim]
    grid_standards: list[SourceClaim]
    safety_emc_standards: list[SourceClaim]
    testing_evidence: list[SourceClaim]
    labeling: list[SourceClaim]