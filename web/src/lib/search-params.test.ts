import { describe, expect, it } from "vitest";

import { parseSearchParams, searchHref, toApiParams } from "@/lib/search-params";

describe("parseSearchParams", () => {
  it("reads a full search", () => {
    const query = parseSearchParams({
      q: "  sleep  ",
      year_from: "2020",
      year_to: "2024",
      availability: "original_annotations_only",
      type: ["review", "article", "review", "book"],
      sort: "newest",
      page: "3",
    });
    expect(query).toEqual({
      q: "sleep",
      yearFrom: 2020,
      yearTo: 2024,
      availability: "original_annotations_only",
      types: ["review", "article"],
      sort: "newest",
      page: 3,
    });
  });

  it("drops invalid values and swaps a reversed year range", () => {
    const query = parseSearchParams({
      q: "x",
      year_from: "2024",
      year_to: "2020",
      availability: "everything",
      sort: "random",
      page: "999",
    });
    expect(query.yearFrom).toBe(2020);
    expect(query.yearTo).toBe(2024);
    expect(query.availability).toBeUndefined();
    expect(query.sort).toBe("relevance");
    expect(query.page).toBe(1);
    expect(parseSearchParams({ q: "x", year_from: "-5" }).yearFrom).toBeUndefined();
  });

  it("treats a missing query as no search", () => {
    expect(parseSearchParams({}).q).toBe("");
  });
});

describe("toApiParams and searchHref", () => {
  const query = parseSearchParams({ q: "vitamin D", type: "review", sort: "oldest", page: "2" });

  it("maps to the API's parameter names", () => {
    expect(toApiParams(query)).toEqual({
      q: "vitamin D",
      year_from: undefined,
      year_to: undefined,
      availability: undefined,
      type: ["review"],
      sort: "oldest",
      page: "2",
    });
  });

  it("builds shareable page links, omitting defaults", () => {
    expect(searchHref(query, { page: 3 })).toBe("/search?q=vitamin+D&type=review&sort=oldest&page=3");
    expect(searchHref(parseSearchParams({ q: "x" }))).toBe("/search?q=x");
  });
});
