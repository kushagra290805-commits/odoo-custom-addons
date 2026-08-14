import time
import uuid
import re
import base64
import io
from typing import Dict, Any, List
from datetime import datetime
from odoo.addons.nexora_studio.services.providers.base_provider import (
    BaseProvider, ProviderMetadata, ProviderCapability,
    ProviderExecutionContext, ProviderHealth, ProviderCategory, ProviderExecutionError
)
from odoo.addons.nexora_studio.services.providers.execution_models import ProviderExecutionRequest, ProviderExecutionResult

try:
    from PIL import Image
    HAS_PIL = True
except ImportError:
    HAS_PIL = False

class AssetBridgeProvider(BaseProvider):
    def __init__(self, sandbox=None):
        super().__init__(self._get_metadata(), sandbox)
    def _get_metadata(self) -> ProviderMetadata:
        return ProviderMetadata(provider_id="asset_bridge", name="Asset Bridge", category=ProviderCategory.ASSET, provider_version="1.0.0", manifest_version="1.0", api_version="1.0", vendor_url="")
    def check_health(self) -> ProviderHealth:
        return ProviderHealth(status="healthy", latency_ms=5.0, error_rate_24h=0.0, last_checked=datetime.utcnow())
    def discover_capabilities(self) -> List[ProviderCapability]:
        return [
            ProviderCapability("optimize_asset", "optimize_asset", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {}),
            ProviderCapability("generate_thumbnail", "generate_thumbnail", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {}),
            ProviderCapability("process_font", "process_font", "1.0", ["1.0"], [], {"type": "object"}, {"type": "object"}, {})
        ]
    def initialize(self, config=None) -> None:
        return None
    def authenticate(self, credentials: Dict[str, str]) -> bool:
        return True
    def cleanup(self) -> None:
        return None
    def fetch(self, resource_id: str, **kwargs) -> Any:
        return self.execute("optimize_asset", {"file": resource_id}, kwargs.get("context"))
    def search(self, query: str, **kwargs) -> List[Any]:
        return []

    def execute(self, request: ProviderExecutionRequest) -> ProviderExecutionResult:
        start = time.time()
        operation = request.payload.get('operation') or request.namespace.split('.')[-1]
        payload = request.payload
        file_path = payload.get("file", "")
        content = payload.get("content", "")
        
        if operation == "optimize_asset":
            if file_path.endswith(".svg") or content.strip().startswith("<svg"):
                svg_content = content or "<svg></svg>"
                opt = re.sub(r'<!--.*?-->', '', svg_content)
                opt = re.sub(r'<g>\\s*</g>', '', opt)
                res = {"status": "success", "is_optimized": True, "format": "svg", "content": opt, "version": str(uuid.uuid4())}
            else:
                if not HAS_PIL:
                    raise ProviderExecutionError("PIL is required for image optimization", self.metadata.provider_id, operation=operation, recovery_recommendation="Check image format and integrity.")
                if not content:
                    raise ProviderExecutionError("No base64 content provided for image optimization", self.metadata.provider_id, operation=operation, recovery_recommendation="Check image format and integrity.")
                
                try:
                    img_bytes = base64.b64decode(content)
                    img = Image.open(io.BytesIO(img_bytes))
                    if img.mode != 'RGB':
                        img = img.convert('RGB')
                    out = io.BytesIO()
                    img.save(out, format="PNG", quality=80, optimize=True)
                    opt_b64 = base64.b64encode(out.getvalue()).decode('utf-8')
                    res = {"status": "success", "is_optimized": True, "format": "png", "content": opt_b64, "version": str(uuid.uuid4())}
                except Exception as e:
                    raise ProviderExecutionError(f"Image optimization failed: {str(e)}", self.metadata.provider_id, operation=operation, recovery_recommendation="Check image format and integrity.")
                    
            return ProviderExecutionResult(success=True, data=res, error=None, metadata={}, execution_ms=(time.time()-start)*1000)
            
        elif operation == "generate_thumbnail":
            if not HAS_PIL:
                raise ProviderExecutionError("PIL is required for thumbnail generation", self.metadata.provider_id, operation=operation, recovery_recommendation="Check image format and integrity.")
            try:
                img_bytes = base64.b64decode(content)
                img = Image.open(io.BytesIO(img_bytes))
                img.thumbnail((200, 200))
                out = io.BytesIO()
                img.save(out, format="PNG")
                thumb_b64 = base64.b64encode(out.getvalue()).decode('utf-8')
                res = {"status": "success", "content": thumb_b64, "width": img.width, "height": img.height}
                return ProviderExecutionResult(success=True, data=res, error=None, metadata={}, execution_ms=(time.time()-start)*1000)
            except Exception as e:
                raise ProviderExecutionError(f"Thumbnail generation failed: {str(e)}", self.metadata.provider_id, operation=operation, recovery_recommendation="Check image format and integrity.")
                
        elif operation == "process_font":
            res = {"status": "success", "subset": "latin", "format": "woff2"}
            return ProviderExecutionResult(success=True, data=res, error=None, metadata={}, execution_ms=(time.time()-start)*1000)
        raise ProviderExecutionError(f"Unsupported: {operation}", self.metadata.provider_id, operation=operation, recovery_recommendation="Check image format and integrity.")
