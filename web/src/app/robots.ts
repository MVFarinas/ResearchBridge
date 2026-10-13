/** robots.txt: index papers and search; keep status pages and development routes out. */
import type { MetadataRoute } from "next";

/**
 * The robots rules.
 *
 * @returns robots.txt content.
 */
export default function robots(): MetadataRoute.Robots {
  return {
    rules: { userAgent: "*", allow: "/", disallow: ["/dev/", "/lookup/requests/"] },
  };
}
