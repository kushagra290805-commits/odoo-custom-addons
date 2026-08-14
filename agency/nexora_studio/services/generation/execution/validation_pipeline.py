from enum import Enum
from typing import Any, List

class ValidationStage(Enum):
    REQUIREMENT = 1
    WEBSITE_PLAN = 2
    PAGE = 3
    ASSET = 4
    COMPONENT = 5
    DOCUMENT = 6

class ValidationPipeline:
    """
    Strict pipeline that halts generation if any stage fails.
    Order: Requirement -> WebsitePlan -> Page -> Asset -> Component -> Document
    """
    def __init__(self):
        self.errors: List[str] = []
        
    def validate(self, stage: ValidationStage, payload: Any) -> bool:
        """
        Executes the specific validation logic for the given stage.
        Returns False if validation fails, stopping generation immediately.
        """
        # Mock validation logic
        if not payload:
            self.errors.append(f"Validation failed at {stage.name}: empty payload.")
            return False
            
        # Specific structural checks would go here based on the stage
        if stage == ValidationStage.COMPONENT:
            # Check for ComponentSchema type, slots, properties, etc.
            pass
            
        return True
        
    def has_errors(self) -> bool:
        return len(self.errors) > 0
