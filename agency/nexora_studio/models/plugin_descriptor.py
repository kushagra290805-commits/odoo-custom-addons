from dataclasses import dataclass, field
from typing import List, Optional

@dataclass(frozen=True)
class PluginDescriptor:
    capability_code: str
    version: str
    display_name: str
    category: str
    author: str
    provider: str
    implementation_model: str
    checksum: str
    supported_platforms: List[str] = field(default_factory=list)
    supports_local: bool = True
    supports_remote: bool = False
    supports_async: bool = False
    permissions: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    optional_dependencies: List[str] = field(default_factory=list)
    minimum_runtime_version: Optional[str] = None
    maximum_runtime_version: Optional[str] = None
    metadata_version: Optional[str] = None
    
    @property
    def capability_id(self) -> str:
        return f"{self.capability_code}.{self.version}"
