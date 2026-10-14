/** The site-wide 404 page. */
import Link from "next/link";

/**
 * The not-found page.
 *
 * @returns The page.
 */
export default function NotFound() {
  return (
    <>
      <h1>Page not found</h1>
      <p className="lede">There is nothing at this address.</p>
      <p>
        Try <Link href="/search">searching</Link> or <Link href="/lookup">looking up a paper</Link>.
      </p>
    </>
  );
}
