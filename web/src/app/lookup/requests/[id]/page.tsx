/**
 * The status page of a paper being prepared after a lookup ("being prepared").
 * It refreshes itself while the worker runs and sends the reader to the paper
 * when it is ready.
 */
import type { Metadata } from "next";
import Link from "next/link";
import { notFound, redirect } from "next/navigation";

import { AutoRefresh } from "@/components/AutoRefresh";
import { apiGet } from "@/lib/api/client";
import type { LookupRequestStatus } from "@/lib/api/types";

/** Seconds between automatic refreshes while preparing. */
const REFRESH_SECONDS = 5;
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

/** Page metadata (status pages are never indexed). */
export const metadata: Metadata = { title: "Preparing a paper", robots: { index: false } };

/** Props Next.js passes to the page. */
interface RequestPageProps {
  /** Route parameters. */
  params: Promise<{ id: string }>;
}

/**
 * The request status page.
 *
 * @returns The page.
 */
export default async function RequestPage({ params }: RequestPageProps) {
  const { id } = await params;
  if (!UUID.test(id)) notFound();
  const request = await apiGet<LookupRequestStatus>(`lookup/requests/${id}/`);
  if (request === null) notFound();
  if (request.status === "ready" && request.paper) redirect(`/papers/${request.paper.key}`);

  return (
    <>
      <h1>{request.status === "preparing" ? "Preparing this paper" : "Lookup result"}</h1>
      <div className={request.status === "preparing" ? "notice info" : "notice"} role="status">
        <p>{request.message}</p>
        <p className="small muted">Requested paper: {request.pmcid}</p>
      </div>
      {request.status === "preparing" ? (
        <>
          <AutoRefresh seconds={REFRESH_SECONDS} />
          <p>
            This page updates by itself. <Link href={`/lookup/requests/${request.id}`}>Check now</Link>
          </p>
        </>
      ) : null}
      {request.links.doi ? (
        <p>
          <a href={request.links.doi} rel="noopener noreferrer">
            Read original paper
          </a>
        </p>
      ) : null}
    </>
  );
}
