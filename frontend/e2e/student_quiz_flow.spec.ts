import { expect, test } from "@playwright/test";
import { backend, registerUser, uniqueEmail } from "./fixtures";

/**
 * Full adaptive flow:
 *   Educator creates + publishes a lesson with a quiz.
 *   Student enrolls, visits the lesson page, takes the quiz.
 *   The backend returns a quiz result → the UI shows the score.
 */
test("student enrolls, visits lesson, submits quiz", async ({ page }) => {
  const api = await backend();
  const ed = await registerUser(api, uniqueEmail("e2e-ed"), "educator");
  const student = await registerUser(api, uniqueEmail("e2e-student"), "student");
  const edHeaders = { Authorization: `Bearer ${ed.access_token}` };
  const studentHeaders = { Authorization: `Bearer ${student.access_token}` };

  const cls = await (await api.post("/classes", { headers: edHeaders, data: { title: "E2E CS", description: "" } })).json();
  await api.post(`/classes/${cls.id}/enroll`, { headers: studentHeaders, data: { enrollment_code: cls.enrollment_code } });

  const material = await (
    await api.post(`/classes/${cls.id}/materials`, {
      headers: edHeaders,
      data: {
        title: "E2E Recursion",
        type: "lesson",
        sections: [
          { title: "Base case", content: "Stopping condition.", order_index: 0 },
          { title: "Recursive step", content: "Reduces the problem.", order_index: 1 }
        ]
      }
    })
  ).json();

  await api.post(`/materials/${material.id}/quiz`, {
    headers: edHeaders,
    data: [
      { question: "What stops recursion?", options: ["Base case", "Timer"], correct_answer: "Base case", points: 1 }
    ]
  });
  const publishResp = await api.put(`/materials/${material.id}/publish`, { headers: edHeaders });
  expect(publishResp.ok()).toBeTruthy();

  await page.goto("/");
  await page.evaluate((value: string) => window.localStorage.setItem("edutrack.auth", value), JSON.stringify(student));
  await page.goto(`/classes/${cls.id}/materials/${material.id}/quiz`);

  await page.getByLabel(/Base case/).check();
  await page.getByRole("button", { name: /submit quiz/i }).click();

  await expect(page.getByText(/Score:/)).toBeVisible({ timeout: 15_000 });
});
