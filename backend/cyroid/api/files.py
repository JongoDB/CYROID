# backend/cyroid/api/files.py
"""File editor API - CRUD operations for text files."""
import os
import shutil
import zipfile
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from uuid import UUID, uuid4

from fastapi import APIRouter, HTTPException, UploadFile, File, Form, status
from pydantic import BaseModel

from cyroid.api.auth import CurrentUser
from cyroid.services.scenario_filesystem import get_scenarios_dir

router = APIRouter(prefix="/files", tags=["files"])


def get_allowed_bases() -> dict[str, Path]:
    """Get allowed base directories for file operations."""
    # In Docker: /images (mounted from ./images)
    # Locally: ./images
    images_path = Path("/images") if os.path.exists("/images") else Path("images")
    return {
        "images": images_path,
        "scenarios": get_scenarios_dir(),
    }

# File size limit for editor (1MB)
MAX_EDITOR_SIZE = 1 * 1024 * 1024

# Supported text file extensions
TEXT_EXTENSIONS = {
    ".dockerfile", ".txt", ".md", ".markdown", ".yaml", ".yml", ".json",
    ".sh", ".bash", ".py", ".conf", ".ini", ".env", ".toml", ".xml",
    ".html", ".css", ".js", ".ts", ".sql", ".cfg", ""  # empty for Dockerfile
}

# In-memory file locks (for MVP - would use Redis/DB in production)
_file_locks: dict[str, dict] = {}


class FileInfo(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified: Optional[datetime] = None
    is_text: bool = True
    locked_by: Optional[str] = None


class FileListResponse(BaseModel):
    path: str
    files: list[FileInfo]
    parent: Optional[str] = None


class FileContentResponse(BaseModel):
    path: str
    content: str
    size: int
    modified: datetime
    locked_by: Optional[str] = None
    lock_token: Optional[str] = None


class CreateFileRequest(BaseModel):
    path: str
    content: str = ""


class UpdateFileRequest(BaseModel):
    path: str
    content: str
    lock_token: Optional[str] = None


class RenameFileRequest(BaseModel):
    old_path: str
    new_path: str


class LockResponse(BaseModel):
    locked: bool
    locked_by: Optional[str] = None
    lock_token: Optional[str] = None
    expires_at: Optional[datetime] = None


def _resolve_path(path: str) -> tuple[Path, str]:
    """Resolve and validate a file path against allowed bases."""
    path = path.strip("/")
    allowed_bases = get_allowed_bases()

    # Determine which base this path belongs to
    for base_name, base_path in allowed_bases.items():
        if path.startswith(base_name + "/") or path == base_name:
            # Security: prevent path traversal
            full_path = (base_path / path.removeprefix(base_name).lstrip("/")).resolve()
            if not str(full_path).startswith(str(base_path.resolve())):
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Path traversal not allowed"
                )
            return full_path, base_name

    raise HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail=f"Path must start with one of: {list(allowed_bases.keys())}"
    )


def _is_text_file(path: Path) -> bool:
    """Check if a file is likely a text file based on extension."""
    # Dockerfile has no extension
    if path.name == "Dockerfile" or path.name.startswith("Dockerfile."):
        return True
    return path.suffix.lower() in TEXT_EXTENSIONS


def _get_language(path: Path) -> str:
    """Get Monaco editor language for a file."""
    name = path.name.lower()
    suffix = path.suffix.lower()

    if name == "dockerfile" or name.startswith("dockerfile."):
        return "dockerfile"

    lang_map = {
        ".yaml": "yaml", ".yml": "yaml",
        ".json": "json",
        ".md": "markdown", ".markdown": "markdown",
        ".sh": "shell", ".bash": "shell",
        ".py": "python",
        ".js": "javascript", ".ts": "typescript",
        ".html": "html", ".css": "css",
        ".xml": "xml",
        ".sql": "sql",
        ".toml": "toml",
        ".ini": "ini", ".conf": "ini", ".cfg": "ini",
        ".env": "shell",
    }
    return lang_map.get(suffix, "plaintext")


def _check_lock(path: str, user_id: str, lock_token: Optional[str] = None) -> Optional[str]:
    """Check if file is locked by another user. Returns lock owner or None."""
    if path not in _file_locks:
        return None

    lock = _file_locks[path]

    # Check if lock expired
    if datetime.utcnow() > lock["expires_at"]:
        del _file_locks[path]
        return None

    # Check if this user owns the lock
    if lock["user_id"] == user_id:
        if lock_token and lock["token"] != lock_token:
            return lock["username"]  # Wrong token
        return None  # User owns lock

    return lock["username"]


@router.get("", response_model=FileListResponse)
def list_files(path: str, current_user: CurrentUser):
    """List files in a directory."""
    full_path, base_name = _resolve_path(path)

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Directory not found: {path}"
        )

    if not full_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Path is not a directory: {path}"
        )

    files = []
    for item in sorted(full_path.iterdir(), key=lambda x: (not x.is_dir(), x.name.lower())):
        item_path = f"{path}/{item.name}".strip("/")
        lock_owner = _check_lock(item_path, str(current_user.id))

        info = FileInfo(
            name=item.name,
            path=item_path,
            is_dir=item.is_dir(),
            size=item.stat().st_size if item.is_file() else None,
            modified=datetime.fromtimestamp(item.stat().st_mtime) if item.exists() else None,
            is_text=_is_text_file(item) if item.is_file() else True,
            locked_by=lock_owner,
        )
        files.append(info)

    # Calculate parent path
    parent = None
    path_parts = path.strip("/").split("/")
    if len(path_parts) > 1:
        parent = "/".join(path_parts[:-1])

    return FileListResponse(path=path, files=files, parent=parent)


@router.get("/content", response_model=FileContentResponse)
def read_file(path: str, current_user: CurrentUser):
    """Read file content."""
    full_path, _ = _resolve_path(path)

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}"
        )

    if full_path.is_dir():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot read directory content"
        )

    # Check file size
    size = full_path.stat().st_size
    if size > MAX_EDITOR_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File too large for editor ({size} bytes, max {MAX_EDITOR_SIZE})"
        )

    # Check if text file
    if not _is_text_file(full_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Binary files cannot be edited. Use download instead."
        )

    try:
        content = full_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="File appears to be binary and cannot be edited"
        )

    # Check lock status
    lock_owner = _check_lock(path, str(current_user.id))
    lock_token = None

    # If not locked, acquire lock for this user
    if not lock_owner and path not in _file_locks:
        lock_token = str(uuid4())
        _file_locks[path] = {
            "user_id": str(current_user.id),
            "username": current_user.username,
            "token": lock_token,
            "expires_at": datetime.utcnow() + timedelta(minutes=30),
        }
    elif path in _file_locks and _file_locks[path]["user_id"] == str(current_user.id):
        lock_token = _file_locks[path]["token"]

    return FileContentResponse(
        path=path,
        content=content,
        size=size,
        modified=datetime.fromtimestamp(full_path.stat().st_mtime),
        locked_by=lock_owner,
        lock_token=lock_token,
    )


@router.post("", response_model=FileContentResponse)
def create_file(request: CreateFileRequest, current_user: CurrentUser):
    """Create a new file."""
    full_path, _ = _resolve_path(request.path)

    if full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"File already exists: {request.path}"
        )

    # Ensure parent directory exists
    full_path.parent.mkdir(parents=True, exist_ok=True)

    # Write file
    full_path.write_text(request.content, encoding="utf-8")

    # Acquire lock
    lock_token = str(uuid4())
    _file_locks[request.path] = {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "token": lock_token,
        "expires_at": datetime.utcnow() + timedelta(minutes=30),
    }

    return FileContentResponse(
        path=request.path,
        content=request.content,
        size=len(request.content.encode("utf-8")),
        modified=datetime.fromtimestamp(full_path.stat().st_mtime),
        lock_token=lock_token,
    )


@router.put("/content")
def update_file(request: UpdateFileRequest, current_user: CurrentUser):
    """Update file content."""
    full_path, _ = _resolve_path(request.path)

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {request.path}"
        )

    # Check lock
    lock_owner = _check_lock(request.path, str(current_user.id), request.lock_token)
    if lock_owner:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"File is locked by {lock_owner}"
        )

    # Write file
    full_path.write_text(request.content, encoding="utf-8")

    # Refresh lock expiry
    if request.path in _file_locks:
        _file_locks[request.path]["expires_at"] = datetime.utcnow() + timedelta(minutes=30)

    return {"success": True, "path": request.path}


@router.put("/rename")
def rename_file(request: RenameFileRequest, current_user: CurrentUser):
    """Rename a file or directory."""
    old_full, _ = _resolve_path(request.old_path)
    new_full, _ = _resolve_path(request.new_path)

    if not old_full.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {request.old_path}"
        )

    if new_full.exists():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Target already exists: {request.new_path}"
        )

    # Check lock on old file
    lock_owner = _check_lock(request.old_path, str(current_user.id))
    if lock_owner:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"File is locked by {lock_owner}"
        )

    # Ensure parent exists
    new_full.parent.mkdir(parents=True, exist_ok=True)

    # Rename
    shutil.move(str(old_full), str(new_full))

    # Transfer lock if exists
    if request.old_path in _file_locks:
        _file_locks[request.new_path] = _file_locks.pop(request.old_path)

    return {"success": True, "old_path": request.old_path, "new_path": request.new_path}


@router.delete("")
def delete_file(path: str, current_user: CurrentUser):
    """Delete a file or directory."""
    full_path, _ = _resolve_path(path)

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}"
        )

    # Check lock
    lock_owner = _check_lock(path, str(current_user.id))
    if lock_owner:
        raise HTTPException(
            status_code=status.HTTP_423_LOCKED,
            detail=f"File is locked by {lock_owner}"
        )

    if full_path.is_dir():
        shutil.rmtree(full_path)
    else:
        full_path.unlink()

    # Remove lock
    _file_locks.pop(path, None)

    return {"success": True, "path": path}


@router.post("/lock", response_model=LockResponse)
def acquire_lock(path: str, current_user: CurrentUser):
    """Acquire a lock on a file."""
    full_path, _ = _resolve_path(path)

    if not full_path.exists():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File not found: {path}"
        )

    # Check existing lock
    lock_owner = _check_lock(path, str(current_user.id))
    if lock_owner:
        return LockResponse(
            locked=False,
            locked_by=lock_owner,
        )

    # Acquire lock
    lock_token = str(uuid4())
    expires_at = datetime.utcnow() + timedelta(minutes=30)
    _file_locks[path] = {
        "user_id": str(current_user.id),
        "username": current_user.username,
        "token": lock_token,
        "expires_at": expires_at,
    }

    return LockResponse(
        locked=True,
        locked_by=current_user.username,
        lock_token=lock_token,
        expires_at=expires_at,
    )


@router.delete("/lock")
def release_lock(path: str, current_user: CurrentUser):
    """Release a lock on a file."""
    if path in _file_locks:
        lock = _file_locks[path]
        if lock["user_id"] == str(current_user.id) or current_user.is_admin:
            del _file_locks[path]
            return {"success": True}
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You don't own this lock"
        )
    return {"success": True}


@router.post("/lock/heartbeat")
def heartbeat_lock(path: str, lock_token: str, current_user: CurrentUser):
    """Keep a lock alive."""
    if path not in _file_locks:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Lock not found"
        )

    lock = _file_locks[path]
    if lock["user_id"] != str(current_user.id) or lock["token"] != lock_token:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Invalid lock token"
        )

    lock["expires_at"] = datetime.utcnow() + timedelta(minutes=30)
    lock["last_heartbeat"] = datetime.utcnow()

    return {"success": True, "expires_at": lock["expires_at"]}


@router.get("/language")
def get_file_language(path: str, current_user: CurrentUser):
    """Get the Monaco editor language for a file."""
    full_path, _ = _resolve_path(path)
    return {"language": _get_language(full_path)}
