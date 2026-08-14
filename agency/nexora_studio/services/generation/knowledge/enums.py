from enum import Enum

class KnowledgeCategory(str, Enum):
    DESIGN_SYSTEM = "design_system"
    DESIGN_TOKEN = "design_token"
    COMPONENT = "component"
    ACCESSIBILITY = "accessibility"
    BRAND = "brand"
    TYPOGRAPHY = "typography"
    LAYOUT = "layout"
    RESPONSIVE = "responsive"
    MOTION = "motion"
    UX_PATTERN = "ux_pattern"

class RetrievalStrategy(str, Enum):
    EXACT = "exact"
    KEYWORD = "keyword"
    SEMANTIC = "semantic"
    HYBRID = "hybrid"

class ProviderType(str, Enum):
    INTERNAL_TEMPLATE = "internal_template"
    FIGMA = "figma"
    PENPOT = "penpot"
    GITHUB = "github"
    MCP = "mcp"
    LOCAL_DOCUMENTATION = "local_documentation"

class ValidationType(str, Enum):
    ACCESSIBILITY = "accessibility"
    TYPOGRAPHY = "typography"
    RESPONSIVE = "responsive"
    COLOR_CONTRAST = "color_contrast"
    DESIGN_TOKEN = "design_token"
    BRAND = "brand"

class KnowledgeDomain(str, Enum):
    DESIGN = "design"
    BRAND = "brand"
    ACCESSIBILITY = "accessibility"
    COMPONENT = "component"
    TEMPLATE = "template"
    LAYOUT = "layout"
