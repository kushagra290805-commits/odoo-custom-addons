from enum import Enum

class DocumentEvent(Enum):
    CREATED = "DocumentCreated"
    LOADED = "DocumentLoaded"
    SAVED = "DocumentSaved"
    NODE_ADDED = "NodeAdded"
    NODE_UPDATED = "NodeUpdated"
    NODE_REMOVED = "NodeRemoved"
    PATCH_APPLIED = "PatchApplied"
    PATCH_ROLLED_BACK = "PatchRolledBack"
