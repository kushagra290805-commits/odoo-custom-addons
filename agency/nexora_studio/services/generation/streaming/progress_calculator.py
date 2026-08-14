class ProgressCalculator:
    """
    Centralized progress computation for the Website Generation Pipeline.
    Engines do not calculate progress; they only report completion.
    """
    _MAPPING = {
        "REQUIREMENTS_CAPTURED": 10,
        "PLANNING_COMPLETED": 20,
        "ARCHITECTURE_COMPLETED": 35,
        "DESIGN_COMPLETED": 50,
        "WORKSPACE_PREPARED": 65,
        "CODE_GENERATION_COMPLETED": 80,
        "VALIDATION_COMPLETED": 95,
        "PREVIEW_READY": 100,
        "DEPLOYMENT_READY": 100,
        "COMPLETED": 100,
        "FAILED": 100,
        "INTERRUPTED": 100
    }

    @classmethod
    def calculate(cls, state: str) -> int:
        """Returns the calculated progress percentage for a given state."""
        return cls._MAPPING.get(state, 0)
