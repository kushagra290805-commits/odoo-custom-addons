import os
import shutil
from pathlib import Path
from typing import Any, List, Optional

class WorkspaceAdapter:
    """
    Sandboxed workspace adapter providing file system operations.
    Prevents directory traversal attacks and ensures operations remain inside the workspace root.
    Engines must use this instead of direct os.path operations.
    """
    def __init__(self, root_path: str, hooks: Any = None):
        self.root = Path(root_path).resolve()
        self._hooks = hooks
        
    def _resolve(self, relative_path: str) -> Path:
        """Resolve a path and ensure it falls within the workspace root."""
        target = (self.root / relative_path).resolve()
        if not target.is_relative_to(self.root):
            raise ValueError(f"Path traversal detected or path outside workspace: {relative_path}")
        return target

    def read_file(self, path: str) -> str:
        target = self._resolve(path)
        with open(target, 'r', encoding='utf-8') as f:
            return f.read()

    def write_file(self, path: str, content: str) -> None:
        if self._hooks:
            self._hooks.before_workspace_write(path, content)
            
        target = self._resolve(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        with open(target, 'w', encoding='utf-8') as f:
            f.write(content)
            
        if self._hooks:
            self._hooks.after_workspace_write(path)

    def exists(self, path: str) -> bool:
        return self._resolve(path).exists()

    def list_dir(self, path: str = ".") -> List[str]:
        target = self._resolve(path)
        if not target.is_dir():
            return []
        return [str(p.relative_to(target)) for p in target.iterdir()]

    def mkdir(self, path: str) -> None:
        target = self._resolve(path)
        target.mkdir(parents=True, exist_ok=True)

    def copy(self, src: str, dest: str) -> None:
        src_target = self._resolve(src)
        dest_target = self._resolve(dest)
        
        if not src_target.exists():
            raise FileNotFoundError(f"Source not found: {src}")
            
        dest_target.parent.mkdir(parents=True, exist_ok=True)
        if src_target.is_dir():
            shutil.copytree(src_target, dest_target, dirs_exist_ok=True)
        else:
            shutil.copy2(src_target, dest_target)

    def move(self, src: str, dest: str) -> None:
        src_target = self._resolve(src)
        dest_target = self._resolve(dest)
        
        if not src_target.exists():
            raise FileNotFoundError(f"Source not found: {src}")
            
        dest_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(src_target, dest_target)

    def delete(self, path: str) -> None:
        target = self._resolve(path)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.is_file() or target.is_symlink():
            target.unlink()

    def import_external_directory(self, src_path: str, dest_relative_path: str = ".", ignore_func=None) -> None:
        """Import an external directory into the workspace safely."""
        src_target = Path(src_path).resolve()
        dest_target = self._resolve(dest_relative_path)
        
        if not src_target.exists():
            raise FileNotFoundError(f"External source not found: {src_path}")
            
        dest_target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copytree(src_target, dest_target, symlinks=True, ignore=ignore_func, dirs_exist_ok=True)

    def check_external_exists(self, path: str) -> bool:
        """Check if an external path exists without escaping the sandbox context."""
        return Path(path).resolve().exists()
