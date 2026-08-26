from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, ConfigDict


class AnalysisRequest(BaseModel):
    intent: str = Field(..., description="Analytical objective")
    target: Optional[str] = None
    mode: str = "fast"
    options: Optional[Dict[str, Any]] = None


class AnalysisResponse(BaseModel):
    status: str
    route: str
    analysis_type: str
    target: Optional[str] = None
    mode: str
    result: Dict[str, Any]
    warnings: List[str] = Field(default_factory=list)


class ProfileFieldManifest(BaseModel):
    model_config = ConfigDict(extra='allow')
    name: str
    role: Optional[str] = None
    storage_type: Optional[str] = None
    measurement_level: Optional[str] = None
    profile: Dict[str, Any] = Field(default_factory=dict)
    distribution: Optional[Dict[str, Any]] = None
    outliers: Optional[Dict[str, Any]] = None
    frequency: Optional[Dict[str, Any]] = None
    temporal: Optional[Dict[str, Any]] = None
    privacy: Optional[Dict[str, Any]] = None


class FeatureEngineeringRecommendationRequest(BaseModel):
    model_config = ConfigDict(extra='allow')
    schema_version: str = '1.0'
    analysis_intent: Dict[str, Any] = Field(default_factory=dict)
    dataset_profile: Dict[str, Any] = Field(default_factory=dict)
    fields: List[ProfileFieldManifest]
    reference_date: Optional[str] = None


class FeatureEngineeringRecommendation(BaseModel):
    id: str
    source_fields: List[str]
    output_field: Optional[str] = None
    operation: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    reason: str
    basis: List[str] = Field(default_factory=list)
    confidence: float
    category: str = 'feature_engineering'
    execution: str = 'browser'
    requires_user_review: bool = True


class FeatureEngineeringRecommendationResponse(BaseModel):
    schema_version: str
    recommender_version: str
    domain_hints: List[str] = Field(default_factory=list)
    recommendations: List[FeatureEngineeringRecommendation] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
