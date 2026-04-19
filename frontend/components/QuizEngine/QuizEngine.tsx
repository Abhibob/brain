"use client";

import { useEffect, useState } from "react";
import { api, QuizQuestion } from "@/lib/api";

export function QuizEngine({ materialId }: { materialId: number }) {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getQuiz(materialId).then(setQuestions).catch((e) => setError(e.message));
  }, [materialId]);

  async function submit() {
    setError(null);
    try {
      const response = await api.submitQuiz(materialId, answers);
      setResult(`Score: ${response.score}/${response.max_score}`);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to submit quiz");
    }
  }

  return (
    <div className="space-y-6">
      {questions.map((question, index) => (
        <div
          key={question.id}
          className="bg-surface-container-lowest rounded-[32px] p-8 border border-surface-dim/20"
        >
          <div className="font-body text-xs uppercase tracking-[0.05em] text-on-surface-variant font-semibold mb-2">
            Question {index + 1}
          </div>
          <h3 className="font-headline text-xl text-primary font-medium mb-5 leading-snug">
            {question.question}
          </h3>
          <div className="space-y-3">
            {question.options.map((option) => (
              <label
                key={option}
                className={`flex items-center gap-3 p-4 rounded-2xl cursor-pointer transition-colors duration-200 ${
                  answers[String(question.id)] === option
                    ? "bg-primary-fixed border border-primary/20"
                    : "bg-surface hover:bg-surface-container-low border border-surface-dim/20"
                }`}
              >
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option}
                  checked={answers[String(question.id)] === option}
                  onChange={() =>
                    setAnswers((current) => ({ ...current, [String(question.id)]: option }))
                  }
                  className="accent-primary w-4 h-4"
                />
                <span className="font-body text-on-surface">{option}</span>
              </label>
            ))}
          </div>
        </div>
      ))}

      {error && (
        <p className="text-error bg-error-container border border-error/30 rounded-xl px-4 py-3 text-sm">
          {error}
        </p>
      )}

      {result && (
        <p className="font-headline text-2xl text-primary font-medium">{result}</p>
      )}

      <button
        className="bg-primary hover:bg-primary-container text-on-primary font-body font-medium px-8 py-4 rounded-full transition-all duration-300 shadow-[0px_10px_20px_rgba(0,45,40,0.15)] flex items-center gap-2"
        onClick={submit}
        disabled={!questions.length}
      >
        Submit quiz
      </button>
    </div>
  );
}
