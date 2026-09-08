from typing import Any
from ..blueprint_models import RawRequirement, ComponentBlueprint

class ComponentSelector:
    """
    Selects abstract component families based on project requirements.

    Phase 47.18 (Part H): a client marketing site always needs the base
    semantic component families (hero, feature/service grid, testimonial,
    contact CTA, footer) so downstream component intelligence has real
    semantics to match source-backed candidates against — the 47.17 E2E
    showed a single abstract component never matched any real candidate.
    Renderer-specific families (3D canvas) remain conditional.
    """
    def select(self, requirement: RawRequirement) -> ComponentBlueprint:
        blueprint = ComponentBlueprint()

        # Base marketing-site component families.
        blueprint.abstract_components.extend([
            "hero_section",
            "feature_grid",
            "testimonial_section",
            "contact_cta",
            "footer",
        ])

        # Abstract mapping (retained for explicit landing-page intents).
        if "landing page" in requirement.intent.lower():
            blueprint.abstract_components.extend(["hero_section", "feature_grid", "footer"])

        if requirement.preferences.get("rendering") == "webgl":
            blueprint.abstract_components.append("3d_canvas_container")

        return blueprint
