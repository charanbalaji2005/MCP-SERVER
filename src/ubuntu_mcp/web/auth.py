"""Authentication and Local Storage Permission Manager for Ubuntu MCP Web Console.

Provides:
- PBKDF2-HMAC-SHA256 password hashing with per-user cryptographic salt
- Device & Local Storage permission consent tracking
- Secure session tokens
- Persistent credential storage in workspace/.auth_config.json
"""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from ..config import SETTINGS

AUTH_FILE = SETTINGS.workspace_root / ".auth_config.json"
SESSIONS_FILE = SETTINGS.workspace_root / ".auth_sessions.json"


def _hash_password(password: str, salt_hex: Optional[str] = None) -> tuple[str, str]:
    """Hash password using PBKDF2-HMAC-SHA256."""
    salt = bytes.fromhex(salt_hex) if salt_hex else secrets.token_bytes(16)
    key = hashlib.pbkdf2_hmac(
        "sha256",
        password.encode("utf-8"),
        salt,
        iterations=100_000,
    )
    return key.hex(), salt.hex()


@dataclass
class UserRecord:
    username: str
    password_hash: str
    salt: str
    storage_permission_granted: bool
    created_at_utc: str
    last_login_utc: Optional[str] = None


class AuthStore:
    def __init__(self, storage_file: Path = AUTH_FILE, sessions_file: Path = SESSIONS_FILE):
        self.file_path = storage_file
        self.sessions_path = sessions_file
        self._sessions: dict[str, str] = {}
        self._users: dict[str, UserRecord] = {}
        self._load()

    def _load(self):
        if self.file_path.exists():
            try:
                data = json.loads(self.file_path.read_text(encoding="utf-8"))
                for u in data.get("users", []):
                    self._users[u["username"]] = UserRecord(**u)
            except Exception:
                pass

        if self.sessions_path.exists():
            try:
                self._sessions = json.loads(self.sessions_path.read_text(encoding="utf-8"))
            except Exception:
                pass

    def _save(self):
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "users": [asdict(u) for u in self._users.values()],
                "updated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            }
            self.file_path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        except Exception as e:
            print(f"[AuthStore] Failed to save auth config: {e}")

    def _save_sessions(self):
        try:
            self.sessions_path.parent.mkdir(parents=True, exist_ok=True)
            self.sessions_path.write_text(json.dumps(self._sessions), encoding="utf-8")
        except Exception:
            pass

    def is_setup_completed(self) -> bool:
        """Return True if at least one user account exists."""
        return len(self._users) > 0

    def register(self, username: str, password: str, storage_permission: bool) -> tuple[bool, str, Optional[str]]:
        """Register the primary user with storage permission."""
        username = username.strip().lower()
        if not username or len(username) < 3:
            return False, "Username must be at least 3 characters long.", None
        if not password or len(password) < 4:
            return False, "Password must be at least 4 characters long.", None
        if username in self._users:
            return False, "Username already exists.", None

        pwd_hash, salt = _hash_password(password)
        now_str = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        user = UserRecord(
            username=username,
            password_hash=pwd_hash,
            salt=salt,
            storage_permission_granted=bool(storage_permission),
            created_at_utc=now_str,
            last_login_utc=now_str,
        )
        self._users[username] = user
        self._save()

        token = self.create_session(username)
        return True, "User registered successfully.", token

    def authenticate(self, username: str, password: str) -> tuple[bool, str, Optional[str]]:
        """Verify username & password and issue a session token."""
        username = username.strip().lower()
        user = self._users.get(username)
        if not user:
            return False, "Invalid username or password.", None

        computed_hash, _ = _hash_password(password, user.salt)
        if not secrets.compare_digest(computed_hash, user.password_hash):
            return False, "Invalid username or password.", None

        user.last_login_utc = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
        self._save()

        token = self.create_session(username)
        return True, "Login successful.", token

    def create_session(self, username: str) -> str:
        token = secrets.token_hex(32)
        self._sessions[token] = username
        self._save_sessions()
        return token

    def validate_session(self, token: Optional[str]) -> Optional[UserRecord]:
        if not token:
            return None
        username = self._sessions.get(token)
        if not username:
            return None
        return self._users.get(username)

    def revoke_session(self, token: str):
        self._sessions.pop(token, None)
        self._save_sessions()


AUTH = AuthStore()

