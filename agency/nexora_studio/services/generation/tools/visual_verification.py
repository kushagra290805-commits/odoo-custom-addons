from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List

@dataclass(frozen=True)
class LayoutValidationResult:
    confidence_score: float
    correction_requests: List[str]
    metadata: Dict[str, Any]

class ScreenshotProvider(ABC):
    @abstractmethod
    def capture(self, target_uri: str) -> bytes:
        pass

class VisionProvider(ABC):
    @abstractmethod
    def analyze(self, image_data: bytes, prompt: str) -> Dict[str, Any]:
        pass

class ConfidenceEvaluator(ABC):
    @abstractmethod
    def evaluate(self, vision_analysis: Dict[str, Any]) -> LayoutValidationResult:
        pass

class VisualVerificationProvider(ABC):
    """Orchestrates the visual verification pipeline."""
    def __init__(self, screenshot: ScreenshotProvider, vision: VisionProvider, evaluator: ConfidenceEvaluator):
        self.screenshot = screenshot
        self.vision = vision
        self.evaluator = evaluator
        
    def verify_layout(self, target_uri: str, prompt: str = "Verify the layout matches design specifications") -> LayoutValidationResult:
        # Step 1: Capture
        img = self.screenshot.capture(target_uri)
        # Step 2: Analyze
        analysis = self.vision.analyze(img, prompt)
        # Step 3: Evaluate
        return self.evaluator.evaluate(analysis)
