/**
 * Reading and writing the search page's URL parameters.
 *
 * The search form is a plain GET form, so a search is a shareable URL and
 * works without JavaScript; these helpers validate what arrives in the URL
 * before it is sent to the API.
 */

/** Sort orders the search offers. */
export type SortOrder = "relevance" | "newest" | "oldest";
/** Corpus availability filters. */
export type AvailabilityFilter = "plain_english_available" | "original_annotations_only";
/** OpenAlex work types the search offers. */
export type WorkType = "article" | "review" | "preprint";

/** A validated search. */
export interface SearchQuery {
  /** Keywords ("" when no search was made). */
  q: string;
  /** Earliest year. */
  yearFrom?: number;
  /** Latest year. */
  yearTo?: number;
  /** Corpus availability filter. */
  availability?: AvailabilityFilter;
  /** OpenAlex work types. */
  types: WorkType[];
  /** Sort order. */
  sort: SortOrder;
  /** 1-based page. */
  page: number;
}

/** Raw URL search parameters as Next.js passes them to pages. */
export type RawParams = Record<string, string | string[] | undefined>;

const SORTS: readonly SortOrder[] = ["relevance", "newest", "oldest"];
const AVAILABILITIES: readonly AvailabilityFilter[] = [
  "plain_english_available",
  "original_annotations_only",
];
const TYPES: readonly WorkType[] = ["article", "review", "preprint"];
const MIN_YEAR = 1600;
const MAX_YEAR = 2100;
const MAX_PAGE = 50;

/**
 * The first value of a parameter.
 *
 * @param value - A raw parameter.
 * @returns Its first value, trimmed, or "".
 */
function first(value: string | string[] | undefined): string {
  return (Array.isArray(value) ? value[0] : value)?.trim() ?? "";
}

/**
 * Parse an integer within bounds.
 *
 * @param value - Raw text.
 * @param min - Smallest allowed value.
 * @param max - Largest allowed value.
 * @returns The integer, or undefined when absent or out of range.
 */
function boundedInt(value: string, min: number, max: number): number | undefined {
  if (!/^\d+$/.test(value)) return undefined;
  const number = Number(value);
  return number >= min && number <= max ? number : undefined;
}

/**
 * Validate the search page's URL parameters; invalid values fall back to defaults.
 *
 * @param raw - The page's search parameters.
 * @returns The search.
 */
export function parseSearchParams(raw: RawParams): SearchQuery {
  const types = (Array.isArray(raw.type) ? raw.type : raw.type ? [raw.type] : []).filter(
    (value): value is WorkType => (TYPES as readonly string[]).includes(value),
  );
  const sort = first(raw.sort);
  const availability = first(raw.availability);
  let yearFrom = boundedInt(first(raw.year_from), MIN_YEAR, MAX_YEAR);
  let yearTo = boundedInt(first(raw.year_to), MIN_YEAR, MAX_YEAR);
  // A reversed range is read as the reader meant it.
  if (yearFrom !== undefined && yearTo !== undefined && yearFrom > yearTo) {
    [yearFrom, yearTo] = [yearTo, yearFrom];
  }
  return {
    q: first(raw.q).slice(0, 300),
    yearFrom,
    yearTo,
    availability: (AVAILABILITIES as readonly string[]).includes(availability)
      ? (availability as AvailabilityFilter)
      : undefined,
    types: [...new Set(types)],
    sort: (SORTS as readonly string[]).includes(sort) ? (sort as SortOrder) : "relevance",
    page: boundedInt(first(raw.page), 1, MAX_PAGE) ?? 1,
  };
}

/**
 * The API query parameters for a search.
 *
 * @param query - The search.
 * @returns Parameters for `GET /api/v1/search/`.
 */
export function toApiParams(query: SearchQuery): Record<string, string | string[] | undefined> {
  return {
    q: query.q,
    year_from: query.yearFrom?.toString(),
    year_to: query.yearTo?.toString(),
    availability: query.availability,
    type: query.types,
    sort: query.sort,
    page: query.page.toString(),
  };
}

/**
 * The URL of the search page for a search (used for pagination links).
 *
 * @param query - The search.
 * @param changes - Fields to change.
 * @returns A relative URL such as `/search?q=sleep&page=2`.
 */
export function searchHref(query: SearchQuery, changes: Partial<SearchQuery> = {}): string {
  const merged = { ...query, ...changes };
  const params = new URLSearchParams();
  params.set("q", merged.q);
  if (merged.yearFrom !== undefined) params.set("year_from", String(merged.yearFrom));
  if (merged.yearTo !== undefined) params.set("year_to", String(merged.yearTo));
  if (merged.availability) params.set("availability", merged.availability);
  for (const type of merged.types) params.append("type", type);
  if (merged.sort !== "relevance") params.set("sort", merged.sort);
  if (merged.page > 1) params.set("page", String(merged.page));
  return `/search?${params.toString()}`;
}
