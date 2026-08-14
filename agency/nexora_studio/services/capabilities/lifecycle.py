from .repository import CapabilityRepository
from .models import CapabilityManifest

class CapabilityLifecycleManager:
    def __init__(self, repository: CapabilityRepository):
        self.repository = repository
        
    def register(self, manifest: CapabilityManifest):
        self.repository.register_manifest(manifest)