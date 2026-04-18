"use client";

import { useEffect, useState } from "react";
import { api, QuizQuestion } from "@/lib/api";

export function QuizEngine({ materialId }: { materialId: number }) {
  const [questions, setQuestions] = useState<QuizQuestion[]>([]);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api.getQuiz(materialId).then(setQuestions).catch(error => setError(error.message));
  }, [materialId]);

  async function submit() {
    setError(null);
    try {
      const response = await api.submitQuiz(materialId, answers);
      setResult(`Score: ${response.score}/${response.max_score}`);
    } catch (error) {
      setError(error instanceof Error ? error.message : "Unable to submit quiz");
    }
  }

  return (
    <div className="stack">
      {questions.map(question => (
        <fieldset className="card" key={question.id}>
          <legend>{question.question}</legend>
          <div className="stack">
            {question.options.map(option => (
              <label key={option}>
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option}
                  checked={answers[String(question.id)] === option}
                  onChange={() => setAnswers(current => ({ ...current, [String(question.id)]: option }))}
                />{" "}
                {option}
              </label>
            ))}
          </div>
        </fieldset>
      ))}
      {error ? <p className="error">{error}</p> : null}
      {result ? <p>{result}</p> : null}
      <button className="button" onClick={submit} disabled={!questions.length}>
        Submit quiz
      </button>
    </div>
  );
}

