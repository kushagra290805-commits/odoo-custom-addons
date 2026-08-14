from .live_preview_engine import LivePreviewEngine
class ComponentPreviewRenderer(LivePreviewEngine):
    def process(self, component: str, props: dict = None, device: str = "desktop") -> dict:
        props_str = " ".join([f'{k}="{v}"' for k, v in (props or {}).items()])
        code = f"<{component} {props_str} />"
        return super().process(code, device)
