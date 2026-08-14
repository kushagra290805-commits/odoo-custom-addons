import json
import logging
from enum import Enum
from odoo import http
from odoo.http import request, Response
from odoo.addons.nexora_studio.services.generation.platform.platform_runtime import PlatformRuntime

_logger = logging.getLogger(__name__)

class SpatialErrorCode(Enum):
    VALIDATION_ERROR = "ERR_VALIDATION"
    NODE_NOT_FOUND = "ERR_NODE_NOT_FOUND"
    TRANSACTION_FAILED = "ERR_TRANSACTION_FAILED"
    SCHEMA_VIOLATION = "ERR_SCHEMA_VIOLATION"
    GENERATION_FAILED = "ERR_GENERATION_FAILED"
    INTERNAL_ERROR = "ERR_INTERNAL"

def api_response(data=None, error_code: SpatialErrorCode=None, message: str=""):
    if error_code:
        return {"status": "error", "error": {"code": error_code.value, "message": message}}
    return {"status": "success", "data": data or {}}

class SpatialAPIController(http.Controller):
    """
    API Gateway endpoints for the Spatial Backend.
    """
    
    def _get_platform(self):
        return request.env['nexora_studio.platform'].get_runtime()

    # ===============================
    # Document Endpoints
    # ===============================
    @http.route('/api/v1/spatial/document/create', type='json', auth='user', methods=['POST'])
    def create_document(self, **kwargs):
        return api_response({"document_id": "doc_123"})

    @http.route('/api/v1/spatial/document/load', type='json', auth='user', methods=['POST'])
    def load_document(self, document_id, **kwargs):
        return api_response({"document": {"id": document_id, "nodes": {}}})

    @http.route('/api/v1/spatial/document/save', type='json', auth='user', methods=['POST'])
    def save_document(self, document_id, payload, **kwargs):
        return api_response()

    @http.route('/api/v1/spatial/document/export', type='json', auth='user', methods=['POST'])
    def export_document(self, document_id, **kwargs):
        return api_response({"json_data": "exported_json"})

    # ===============================
    # Patch Endpoints
    # ===============================
    @http.route('/api/v1/spatial/patch/apply', type='json', auth='user', methods=['POST'])
    def apply_patch(self, document_id, patch, **kwargs):
        return api_response()

    @http.route('/api/v1/spatial/patch/batch', type='json', auth='user', methods=['POST'])
    def batch_patch(self, document_id, patches, **kwargs):
        return api_response()

    @http.route('/api/v1/spatial/patch/commit', type='json', auth='user', methods=['POST'])
    def commit_transaction(self, document_id, **kwargs):
        return api_response()

    @http.route('/api/v1/spatial/patch/rollback', type='json', auth='user', methods=['POST'])
    def rollback_patch(self, document_id, **kwargs):
        return api_response()

    # ===============================
    # Component Endpoints
    # ===============================
    @http.route('/api/v1/spatial/component/registry', type='json', auth='user', methods=['GET'])
    def get_component_registry(self, **kwargs):
        return api_response({"components": []})

    # ===============================
    # Theme Endpoints
    # ===============================
    @http.route('/api/v1/spatial/theme/active', type='json', auth='user', methods=['GET'])
    def get_active_theme(self, **kwargs):
        return api_response({"theme": "light"})

    # ===============================
    # Asset Endpoints
    # ===============================
    @http.route('/api/v1/spatial/asset/upload', type='http', auth='user', methods=['POST'], csrf=False)
    def upload_asset(self, **kwargs):
        res = api_response({"asset_id": "asset://123"})
        return request.make_response(json.dumps(res), headers=[('Content-Type', 'application/json')])

    # ===============================
    # AI Generation Endpoints
    # ===============================
    @http.route('/api/v1/spatial/generate/component', type='json', auth='user', methods=['POST'])
    def generate_component(self, prompt, context, **kwargs):
        # Must invoke PlatformRuntime!
        return api_response({"patch": {}})

    # ===============================
    # Plugin Endpoints
    # ===============================
    @http.route('/api/v1/spatial/plugin/registry', type='json', auth='user', methods=['GET'])
    def get_plugin_registry(self, **kwargs):
        return api_response({"plugins": []})

    # ===============================
    # WebSocket Streaming Mock
    # ===============================
    @http.route('/api/v1/spatial/stream/events', type='http', auth='user', methods=['GET'])
    def stream_events(self, **kwargs):
        return request.make_response("stream_ready", headers=[('Content-Type', 'text/plain')])
