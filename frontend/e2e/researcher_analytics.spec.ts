import { expect, test } from "@playwright/test";
import { backend, registerUser, uniqueEmail } from "./fixtures";

test("researcher reads class roster", async ({ page }) => {
  const api = await backend();
  const educator = await registerUser(api, uniqueEmail("e2e-edr"), "educator");
  const researcher = await registerUser(api, uniqueEmail("e2e-res"), "researcher");
  const student = await registerUser(api, uniqueEmail("e2e-stu"), "student");

  const edHeaders = { Authorization: `Bearer ${educator.access_token}` };
  const stuHeaders = { Authorization: `Bearer ${student.access_token}` };

  const cls = await (
    await api.post("/classes", { headers: edHeaders, data: { title: "E2E Research Class", description: "" } })
  ).json();
  await api.post(`/classes/${cls.id}/enroll`, { headers: stuHeaders, data: { enrollment_code: cls.enrollment_code } });

  await page.goto("/");
  await page.evaluate((value: string) => window.localStorage.setItem("edutrack.auth", value), JSON.stringify(researcher));
  await page.goto(`/classes/${cls.id}`);

  await expect(page.getByText(/E2E Research Class/)).toBeVisible({ timeout: 15_000 });
});
