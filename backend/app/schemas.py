from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field

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
    warnings: List[str] = []
