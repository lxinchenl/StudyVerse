import hashlib
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

CHAPTER_PATTERN = re.compile(r"第(\d+)章")
SUPPORTED_SUFFIXES = {".pptx", ".docx", ".doc", ".pdf", ".md", ".txt", ".markdown"}
MATERIALS_SUBDIR = "materials"


@dataclass(frozen=True)
class CourseInfo:
    id: str
    title: str
    description: str
    root: Path
    materials_dir: Path


@dataclass(frozen=True)
class MaterialFile:
    id: str
    course_id: str
    path: Path
    relative_path: str
    title: str
    chapter_key: str
    chapter_title: str
    chapter_order: int
    doc_type: str
    pages: int | None = None


@dataclass
class CourseCatalog:
    courses_dir: Path
    courses: dict[str, CourseInfo] = field(default_factory=dict)
    chapters: dict[str, dict[str, dict]] = field(default_factory=dict)
    materials: dict[str, list[MaterialFile]] = field(default_factory=dict)
    material_by_id: dict[str, MaterialFile] = field(default_factory=dict)

    @classmethod
    def discover(cls, courses_dir: Path) -> "CourseCatalog":
        catalog = cls(courses_dir=courses_dir)
        if not courses_dir.exists():
            courses_dir.mkdir(parents=True, exist_ok=True)
            return catalog

        for course_dir in sorted(p for p in courses_dir.iterdir() if p.is_dir()):
            course = _load_course_info(course_dir)
            chapter_meta, materials = _scan_course_materials(course)
            if not materials:
                continue
            catalog.courses[course.id] = course
            catalog.chapters[course.id] = chapter_meta
            catalog.materials[course.id] = materials
            for material in materials:
                catalog.material_by_id[material.id] = material
        return catalog

    def list_courses(self) -> list[CourseInfo]:
        return list(self.courses.values())

    def get_course(self, course_id: str) -> CourseInfo | None:
        return self.courses.get(course_id)

    def list_chapters(self, course_id: str) -> list[dict]:
        meta = self.chapters.get(course_id, {})
        return sorted(meta.values(), key=lambda c: c["order"])

    def list_materials(self, course_id: str) -> list[MaterialFile]:
        return self.materials.get(course_id, [])

    def get_material(self, doc_id: str) -> MaterialFile | None:
        return self.material_by_id.get(doc_id)


def _load_course_info(course_dir: Path) -> CourseInfo:
    course_id = course_dir.name
    meta_path = course_dir / "course.json"
    title = course_id
    description = ""
    if meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        title = meta.get("title", title)
        description = meta.get("description", description)

    materials_dir = course_dir / MATERIALS_SUBDIR
    if not materials_dir.exists():
        materials_dir = course_dir
    return CourseInfo(
        id=course_id,
        title=title,
        description=description,
        root=course_dir,
        materials_dir=materials_dir,
    )


def _doc_id(course_id: str, relative_path: str) -> str:
    return hashlib.md5(f"{course_id}/{relative_path}".encode("utf-8")).hexdigest()


def _chapter_info(stem: str) -> tuple[str, str, int]:
    match = CHAPTER_PATTERN.search(stem)
    if not match:
        return "ch-other", "实验与其他资料", 99
    number = int(match.group(1))
    chapter_key = f"ch{number}"
    rest = stem[match.end() :].strip()
    lecture = re.search(r"第\d+讲", rest)
    if lecture:
        rest = rest[: lecture.start()].strip()
    chapter_title = f"第{number}章 {rest}".strip() if rest else f"第{number}章"
    return chapter_key, chapter_title, number


def _iter_material_files(materials_dir: Path) -> list[Path]:
    files: list[Path] = []
    for path in sorted(materials_dir.rglob("*")):
        if not path.is_file():
            continue
        if path.name.startswith("~$"):
            continue
        if path.suffix.lower() in SUPPORTED_SUFFIXES:
            files.append(path)
    return files


def _scan_course_materials(course: CourseInfo) -> tuple[dict[str, dict], list[MaterialFile]]:
    chapter_meta: dict[str, dict] = {}
    materials: list[MaterialFile] = []

    for path in _iter_material_files(course.materials_dir):
        relative = path.relative_to(course.materials_dir).as_posix()
        chapter_key, chapter_title, chapter_order = _chapter_info(path.stem)
        if chapter_key not in chapter_meta:
            chapter_meta[chapter_key] = {
                "id": chapter_key,
                "title": chapter_title,
                "order": chapter_order,
            }
        doc_type = path.suffix.lower().lstrip(".")
        if doc_type == "doc":
            doc_type = "docx"
        if doc_type == "markdown":
            doc_type = "markdown"
        materials.append(
            MaterialFile(
                id=_doc_id(course.id, relative),
                course_id=course.id,
                path=path,
                relative_path=relative,
                title=path.stem,
                chapter_key=chapter_key,
                chapter_title=chapter_meta[chapter_key]["title"],
                chapter_order=chapter_order,
                doc_type=doc_type,
            )
        )
    return chapter_meta, materials
