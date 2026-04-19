import { expect, test } from "@playwright/test";
import { backend, registerUser, uniqueEmail } from "./fixtures";

test("research workbench renders mechanistic panels and nonblank TRIBE canvas", async ({ page }) => {
  const api = await backend();
  const educator = await registerUser(api, uniqueEmail("e2e-work-ed"), "educator");
  const researcher = await registerUser(api, uniqueEmail("e2e-work-res"), "researcher");
  const student = await registerUser(api, uniqueEmail("e2e-work-stu"), "student");

  const edHeaders = { Authorization: `Bearer ${educator.access_token}` };
  const stuHeaders = { Authorization: `Bearer ${student.access_token}` };

  const cls = await (
    await api.post("/classes", { headers: edHeaders, data: { title: "E2E Neuro Class", description: "workbench" } })
  ).json();
  await api.post(`/classes/${cls.id}/enroll`, { headers: stuHeaders, data: { enrollment_code: cls.enrollment_code } });
  await api.post(`/classes/${cls.id}/materials`, {
    headers: edHeaders,
    data: {
      title: "Neural evidence in reading",
      type: "lesson",
      sections: [
        { title: "Signal", content: "A neural signal changes as a learner reads and answers.", order_index: 0 },
        { title: "Trace", content: "We inspect activations, gradients, and response predictions.", order_index: 1 }
      ]
    }
  });

  await page.route("**/research/materials/*/students/*/tribe", async route => {
    if (route.request().method() === "POST") {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          status: "complete",
          prediction: {
            id: 1,
            student_id: student.user.id,
            material_id: 1,
            personalized_lesson_id: null,
            stimulus_hash: "abc",
            stimulus_title: "Neural evidence in reading",
            stimulus_kind: "base_lesson",
            model_version: "tribe-v2-e2e",
            hemodynamic_lag_s: 5,
            roi_timeseries: {
              V1: [0.12, 0.3, 0.48, 0.2],
              IFG: [-0.18, -0.08, 0.05, 0.11],
              STS: [0.04, 0.12, 0.22, 0.34]
            },
            roi_summary: {},
            connectivity: [
              { source: "V1", target: "IFG", weight: -0.42 },
              { source: "STS", target: "IFG", weight: 0.61 }
            ],
            surface_summary: { space: "fsaverage5", vertex_count: 20484, frame_count: 4 },
            error: null,
            created_at: new Date().toISOString(),
            completed_at: new Date().toISOString()
          }
        })
      });
      return;
    }
    await route.fulfill({
      status: 200,
      contentType: "application/json",
      body: JSON.stringify({ status: "not_requested", prediction: null })
    });
  });

  await page.goto("/");
  await page.evaluate((value: string) => window.localStorage.setItem("edutrack.auth", value), JSON.stringify(researcher));
  await page.goto(`/research/classes/${cls.id}/workbench`);

  await expect(page.getByText("Research Workbench")).toBeVisible({ timeout: 15_000 });
  await expect(page.getByText("Student Console")).toBeVisible();
  await expect(page.getByText("Neural Microscope")).toBeVisible();
  await expect(page.getByText("Expandable Backprop Heatmaps")).toBeVisible();
  await expect(page.getByRole("button", { name: "Activation-weighted influence" })).toBeVisible();
  await page.getByRole("button", { name: /Loss gradient/i }).click();
  await expect(page.getByText("Selected mechanism")).toBeVisible();
  await page.locator(".matrix-heatmap__cell").first().click();
  await expect(page.locator(".cell-inspector").getByText(/loss sensitivity|local contribution|learned association/i)).toBeVisible();
  await page.getByRole("button", { name: /H1 -> H2/i }).click();
  await page.getByRole("button", { name: /Update pressure/i }).click();
  await expect(page.getByRole("button", { name: "Update pressure" })).toBeVisible();
  await expect(page.getByText("Personalization Audit")).toBeVisible();
  await expect(page.getByText("TRIBE Neuroview")).toBeVisible();

  await page.getByRole("button", { name: /Run TRIBE v2/i }).click();
  const canvas = page.locator(".neuro-scene canvas");
  await expect(canvas).toBeVisible({ timeout: 15_000 });
  await expect.poll(async () => canvas.evaluate((node: HTMLCanvasElement) => node.toDataURL("image/png").length)).toBeGreaterThan(1_000);
});
