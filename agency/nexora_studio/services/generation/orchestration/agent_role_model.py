from enum import Enum

class AgentRole(str, Enum):
    PLANNER = "planner"             # Breaks down the user prompt
    ARCHITECT = "architect"         # Designs the file structure
    DESIGNER = "designer"           # Curates the brand tokens
    FRONTEND = "frontend"           # Writes the React/Vue code
    BACKEND = "backend"             # Writes the Python/Node code
    ACCESSIBILITY = "accessibility" # Enforces WCAG
    REVIEWER = "reviewer"           # Acts as QA
    OPTIMIZER = "optimizer"         # Refactors for performance
    DEPLOYMENT = "deployment"       # Handles the CI/CD pipeline
    CUSTOM = "custom"               # User-defined agents
    
class NodeType(str, Enum):
    AGENT_EXECUTION = "agent_execution"
    HUMAN_APPROVAL = "human_approval"
    CONDITION = "condition"

class WorkflowState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
