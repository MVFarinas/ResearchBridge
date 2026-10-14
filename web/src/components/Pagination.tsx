/** Previous / next links for search results. */
import Link from "next/link";

import { type SearchQuery, searchHref } from "@/lib/search-params";

/** Props of {@link Pagination}. */
export interface PaginationProps {
  /** The current search. */
  query: SearchQuery;
  /** Whether a further page exists in either result list. */
  hasNext: boolean;
}

/**
 * Pagination links; nothing is rendered when there is only one page.
 *
 * @returns The navigation, or null.
 */
export function Pagination({ query, hasNext }: PaginationProps) {
  if (query.page <= 1 && !hasNext) return null;
  return (
    <nav className="pagination" aria-label="Result pages">
      {query.page > 1 ? (
        <Link href={searchHref(query, { page: query.page - 1 })} rel="prev">
          Previous page
        </Link>
      ) : null}
      <span className="muted">Page {query.page}</span>
      {hasNext ? (
        <Link href={searchHref(query, { page: query.page + 1 })} rel="next">
          Next page
        </Link>
      ) : null}
    </nav>
  );
}
