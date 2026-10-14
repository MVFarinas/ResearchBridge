/**
 * The search form: a plain GET form to `/search`, so it works without
 * JavaScript and every search is a shareable URL.
 */
import type { SearchQuery } from "@/lib/search-params";

/** Props of {@link SearchForm}. */
export interface SearchFormProps {
  /** The current search, to prefill the fields. */
  query?: SearchQuery;
  /** Whether the filter panel starts open. */
  filtersOpen?: boolean;
}

/**
 * Keyword search with filters (years, availability, work type) and a date sort.
 *
 * @returns The form.
 */
export function SearchForm({ query, filtersOpen = false }: SearchFormProps) {
  const types = new Set(query?.types ?? []);
  return (
    <form className="search-form" action="/search" method="get" role="search">
      <div className="search-row">
        <label htmlFor="q" className="visually-hidden">
          Search papers
        </label>
        <input
          id="q"
          name="q"
          type="search"
          required
          maxLength={300}
          defaultValue={query?.q ?? ""}
          placeholder="Search papers, e.g. vitamin D and sleep"
          autoComplete="off"
        />
        <button className="button" type="submit">
          Search
        </button>
      </div>
      <details className="filters" open={filtersOpen}>
        <summary>Filters and sorting</summary>
        <div className="filter-grid">
          <fieldset>
            <legend>Published</legend>
            <div className="year-range">
              <label htmlFor="year_from" className="visually-hidden">
                From year
              </label>
              <input
                id="year_from"
                name="year_from"
                type="number"
                min={1600}
                max={2100}
                inputMode="numeric"
                placeholder="From"
                defaultValue={query?.yearFrom}
              />
              <span aria-hidden="true">to</span>
              <label htmlFor="year_to" className="visually-hidden">
                To year
              </label>
              <input
                id="year_to"
                name="year_to"
                type="number"
                min={1600}
                max={2100}
                inputMode="numeric"
                placeholder="To"
                defaultValue={query?.yearTo}
              />
            </div>
          </fieldset>
          <div>
            <label htmlFor="availability">On ResearchBridge</label>
            <select id="availability" name="availability" defaultValue={query?.availability ?? ""}>
              <option value="">Any</option>
              <option value="plain_english_available">Plain English permitted</option>
              <option value="original_annotations_only">Original + explanations only</option>
            </select>
          </div>
          <fieldset>
            <legend>Type (wider search)</legend>
            {(["article", "review", "preprint"] as const).map((type) => (
              <label className="choice" key={type}>
                <input type="checkbox" name="type" value={type} defaultChecked={types.has(type)} />
                {type === "article" ? "Articles" : type === "review" ? "Reviews" : "Preprints"}
              </label>
            ))}
          </fieldset>
          <div>
            <label htmlFor="sort">Sort by</label>
            <select id="sort" name="sort" defaultValue={query?.sort ?? "relevance"}>
              <option value="relevance">Relevance</option>
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </div>
        </div>
      </details>
    </form>
  );
}
