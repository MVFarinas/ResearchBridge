import { expect, test } from "@playwright/test";

/** The search term used against the local development corpus. */
const QUERY = process.env.E2E_QUERY || "vitamin D";

test("search, open a paper, and see its licence and honest empty states", async ({ page }) => {
  await page.goto("/");
  await page.getByRole("searchbox", { name: "Search papers" }).fill(QUERY);
  await page.getByRole("button", { name: "Search" }).click();

  // Results from the corpus carry an availability tag and link to the paper page.
  const corpus = page.getByRole("region", { name: "Readable on ResearchBridge" });
  await expect(corpus).toBeVisible();
  const first = corpus.getByRole("listitem").first();
  await expect(first.locator(".tag").first()).toBeVisible();
  await first.getByRole("heading").getByRole("link").click();

  // The paper page shows the original, the licence block and outbound links.
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("link", { name: "Original + explanations" })).toHaveAttribute(
    "aria-current",
    "page",
  );
  await expect(page.getByRole("region", { name: "Licence and attribution" })).toContainText(
    "does not imply endorsement by NLM",
  );
  await expect(page.getByRole("link", { name: "Read original paper" })).toHaveAttribute(
    "href",
    /^https:\/\/doi\.org\//,
  );
  await expect(page.getByText(/as of \d+ \w+ \d{4}/).first()).toBeVisible();

  // The plain-English view is an empty state, never invented text.
  await page.getByRole("link", { name: "Plain English" }).click();
  await expect(page.getByRole("heading", { name: /not written yet|No plain-English/ })).toBeVisible();
});

test("lookup of an arXiv ID explains it is not available here", async ({ page }) => {
  await page.goto("/lookup");
  await page.getByLabel("DOI, PubMed ID, PMC ID, arXiv ID or title").fill("arXiv:2310.06825");
  await page.getByRole("button", { name: "Look up" }).click();
  await expect(page.getByRole("status")).toContainText("arXiv");
  await expect(page.getByRole("link", { name: "Read it on arXiv" })).toHaveAttribute(
    "href",
    "https://arxiv.org/abs/2310.06825",
  );
});

test("the synthetic demo is not served by a production build", async ({ page }) => {
  const response = await page.goto("/dev/annotations-demo");
  expect(response?.status()).toBe(404);
});
