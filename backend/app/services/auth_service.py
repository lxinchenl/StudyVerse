import json
import re
from datetime import datetime, timezone
from pathlib import Path

from app.domain.schemas import UserOut
from app.infrastructure.password_hash import hash_password, verify_password

DEFAULT_ME = {
    "role": "高校课程学习助手",
    "tone": "耐心、清晰",
    "boundaries": "基于课程资料回答，不确定时明确说明",
}

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class AuthService:
    def __init__(self, users_dir: Path):
        self.users_dir = users_dir
        self.users_dir.mkdir(parents=True, exist_ok=True)

    def list_users(self) -> list[UserOut]:
        users: list[UserOut] = []
        for path in sorted(self.users_dir.iterdir()):
            if not path.is_dir():
                continue
            meta = self._read_user_meta(path)
            if meta:
                users.append(UserOut(**meta))
        return users

    def get_user(self, user_id: str) -> UserOut | None:
        meta_path = self.users_dir / user_id / "user.json"
        if not meta_path.exists():
            return None
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return UserOut(
            id=str(data.get("id") or user_id),
            name=str(data.get("name") or ""),
            major=str(data.get("major") or ""),
            email=str(data.get("email") or ""),
        )

    def register(self, name: str, email: str, password: str, major: str = "") -> UserOut:
        cleaned_name = name.strip()
        cleaned_email = email.strip().lower()
        if not cleaned_name:
            raise ValueError("姓名不能为空")
        if not _EMAIL_RE.match(cleaned_email):
            raise ValueError("邮箱格式无效")
        if len(password) < 6:
            raise ValueError("密码至少 6 位")
        if self._email_exists(cleaned_email):
            raise ValueError("该邮箱已注册")

        user_id = f"u{int(datetime.now(timezone.utc).timestamp())}"
        user_dir = self.users_dir / user_id
        user_dir.mkdir(parents=True, exist_ok=False)
        (user_dir / "memory").mkdir()
        (user_dir / "conversation_memory").mkdir()
        (user_dir / "uploads").mkdir()
        meta = {
            "id": user_id,
            "name": cleaned_name,
            "major": major.strip(),
            "email": cleaned_email,
            "password_hash": hash_password(password),
        }
        (user_dir / "user.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
        (user_dir / "me.json").write_text(json.dumps(DEFAULT_ME, ensure_ascii=False, indent=2), encoding="utf-8")
        profile = {
            "student_id": user_id,
            "major": major.strip(),
            "course": "",
            "goal": "",
            "recent_topics": [],
            "weak_points": [],
            "frequent_errors": [],
            "preferences": [],
            "mastery": {},
        }
        (user_dir / "user_profile.json").write_text(json.dumps(profile, ensure_ascii=False, indent=2), encoding="utf-8")
        return UserOut(id=user_id, name=cleaned_name, major=major.strip(), email=cleaned_email)

    def login(self, email: str, password: str) -> UserOut:
        cleaned_email = email.strip().lower()
        if not cleaned_email or not password:
            raise ValueError("邮箱和密码不能为空")
        record = self._find_by_email(cleaned_email)
        if record is None:
            raise ValueError("邮箱或密码错误")
        stored_hash = str(record.get("password_hash") or "")
        if not stored_hash or not verify_password(password, stored_hash):
            raise ValueError("邮箱或密码错误")
        return UserOut(
            id=str(record["id"]),
            name=str(record.get("name") or ""),
            major=str(record.get("major") or ""),
            email=cleaned_email,
        )

    def _email_exists(self, email: str) -> bool:
        return self._find_by_email(email) is not None

    def _find_by_email(self, email: str) -> dict | None:
        for path in self.users_dir.iterdir():
            if not path.is_dir():
                continue
            meta_path = path / "user.json"
            if not meta_path.exists():
                continue
            try:
                data = json.loads(meta_path.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            if str(data.get("email") or "").strip().lower() == email:
                return data
        return None

    @staticmethod
    def _read_user_meta(user_dir: Path) -> dict[str, str] | None:
        meta_path = user_dir / "user.json"
        if not meta_path.exists():
            return None
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        return {
            "id": str(data.get("id") or user_dir.name),
            "name": str(data.get("name") or ""),
            "major": str(data.get("major") or ""),
            "email": str(data.get("email") or ""),
        }
