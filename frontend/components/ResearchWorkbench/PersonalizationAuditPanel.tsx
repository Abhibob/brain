"use client";

import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import { PersonalizationAudit } from "@/lib/api";

export function PersonalizationAuditPanel({ audit }: { audit: PersonalizationAudit | null }) {
  return (
    <section className="research-panel">
      <div className="research-panel__header">
        <div>
          <div className="research-kicker">Personalization Audit</div>
          <h2>Base content, retrieved profile evidence, and generated lesson</h2>
        </div>
        {audit && <span className="research-pill">{audit.personalized ? "personalized ready" : "base fallback"}</span>}
      </div>

      {!audit ? (
        <p className="muted">Choose a student and material to inspect the personalization path.</p>
      ) : (
        <div className="audit-layout">
          <div className="audit-column">
            <div className="research-viz__title">Original lesson</div>
            <div className="audit-scroll">
              {audit.base_lesson.sections.map(section => (
                <article key={section.id} className="audit-section">
                  <h3>{section.title}</h3>
                  <p>{section.content}</p>
                </article>
              ))}
            </div>
          </div>

          <div className="audit-column">
            <div className="research-viz__title">Retrieved profile entries</div>
            <div className="audit-scroll">
              {audit.retrieved_profile_entries.length ? (
                audit.retrieved_profile_entries.map(entry => (
                  <article key={entry.id} className="audit-section audit-section--signal">
                    <h3>{new Date(entry.created_at).toLocaleString()}</h3>
                    <p>{entry.profile_text}</p>
                    {entry.quiz_score !== null && <span className="research-pill">quiz {(entry.quiz_score * 100).toFixed(0)}%</span>}
                  </article>
                ))
              ) : (
                <p className="muted">No profile entries were retrieved for this lesson yet.</p>
              )}
            </div>
          </div>

          <div className="audit-column audit-column--wide">
            <div className="research-viz__title">Personalized markdown render</div>
            <div className="audit-scroll markdown-body">
              {audit.personalized_lesson ? (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>{audit.personalized_lesson.generated_content}</ReactMarkdown>
              ) : (
                <ReactMarkdown remarkPlugins={[remarkGfm]}>
                  {`# ${audit.base_lesson.title}\n\n${audit.base_lesson.sections
                    .map(section => `## ${section.title}\n\n${section.content}`)
                    .join("\n\n")}`}
                </ReactMarkdown>
              )}
            </div>
          </div>
        </div>
      )}
    </section>
  );
}
