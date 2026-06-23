"use client";

import { useState } from "react";
import Link from "next/link";
import { ChevronDown, FileText } from "lucide-react";

import type { Chapter, CourseDocument } from "@/lib/types";
import { DOC_TYPE_LABELS } from "@/lib/constants";

export function ChapterAccordion({
  chapters,
  documents,
  courseId
}: {
  chapters: Chapter[];
  documents: CourseDocument[];
  courseId: string;
}) {
  const [openId, setOpenId] = useState<string | null>(chapters[0]?.id ?? null);
  const getDocTypeClass = (type: CourseDocument["type"]) => {
    if (type === "pptx") return "course-outline-doc-type--ppt";
    if (type === "pdf") return "course-outline-doc-type--pdf";
    if (type === "docx") return "course-outline-doc-type--word";
    return "";
  };

  return (
    <div className="course-outline">
      {chapters.map((chapter) => {
        const docs = documents.filter((d) => d.chapterId === chapter.id);
        const isOpen = openId === chapter.id;
        return (
          <article key={chapter.id} className="course-outline-item">
            <button
              type="button"
              className={`course-outline-header ${isOpen ? "open" : ""}`}
              onClick={() => setOpenId(isOpen ? null : chapter.id)}
            >
              <span className="course-outline-header-main">
                <span className="course-outline-order">{chapter.order}</span>
                <span>
                  <strong>{chapter.title}</strong>
                  <em>{docs.length} 份资料</em>
                </span>
              </span>
              <ChevronDown size={18} className={`course-outline-chevron ${isOpen ? "rotated" : ""}`} />
            </button>
            {isOpen ? (
              <div className="course-outline-body">
                {docs.length === 0 ? (
                  <p className="muted">本章暂未上传资料</p>
                ) : (
                  <div className="course-outline-doc-list">
                    {docs.map((doc) => (
                      <div key={doc.id} className="course-outline-doc-item">
                        <div className="course-outline-doc-main">
                          <div className="course-outline-doc-icon">
                            <FileText size={16} />
                          </div>
                          <div>
                            <div className="course-outline-doc-title-row">
                              <strong>{doc.title}</strong>
                              <span className={`course-outline-doc-type ${getDocTypeClass(doc.type)}`}>
                                {DOC_TYPE_LABELS[doc.type]}
                              </span>
                            </div>
                            <p className="muted">
                              进度 {doc.progress}%
                              {doc.pages ? ` · ${doc.pages} 页` : ""}
                            </p>
                            <div className="progress-bar course-outline-doc-progress">
                              <i style={{ width: `${doc.progress}%` }} />
                            </div>
                          </div>
                        </div>
                        <Link href={`/courses/${courseId}/read/${doc.id}`} className="btn-secondary">
                          阅读
                        </Link>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : null}
          </article>
        );
      })}
    </div>
  );
}
