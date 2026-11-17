import { useEffect, useMemo, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { deleteJob, errorMessage, listJobs } from "../api/client";
import type { JobSummary } from "../api/types";
import { JobTable } from "./DashboardPage";
import { AppShell } from "../components/Shell";
import { Dialog, EmptyState } from "../components/ui";
import { useToast } from "../context/ToastContext";

const filters = ["all", "video", "image", "audio", "document", "suspicious", "completed", "failed"] as const;

export function HistoryPage() {
  const [params, setParams] = useSearchParams();
  const status = params.get("status");
  const active = status === "completed" ? "completed" : params.get("filter") ?? "all";
  const [jobs, setJobs] = useState<JobSummary[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState("");
  const [page, setPage] = useState(0);
  const [pending, setPending] = useState<JobSummary | null>(null);
  const { push } = useToast();

  async function load() {
    try {
      setJobs(await listJobs());
    } catch (reason) {
      setError(errorMessage(reason, "Investigation history could not be loaded."));
    }
  }

  useEffect(() => {
    void load();
  }, []);

  const filtered = useMemo(() => {
    return jobs.filter((job) => {
      if (query && !job.file_name.toLowerCase().includes(query.toLowerCase())) return false;
      if (active === "all") return true;
      if (active === "suspicious") return job.classification === "high" || job.classification === "critical";
      if (active === "completed" || active === "failed") return job.status === active;
      if (active === "document") return job.category === "document" || job.category === "data";
      return job.category === active;
    });
  }, [jobs, query, active]);
  const pageSize = 8;
  const visible = filtered.slice(page * pageSize, page * pageSize + pageSize);
  const pages = Math.max(1, Math.ceil(filtered.length / pageSize));

  return (
    <AppShell title="Your Investigation History" subtitle="Records from this account. Filters do not add files that were never analyzed.">
      <div className="mb-4 flex flex-wrap gap-2">
        {filters.map((filter) => (
          <button
            key={filter}
            type="button"
            className={`btn ${active === filter ? "btn-primary" : "btn-secondary"}`}
            onClick={() => {
              setPage(0);
              if (filter === "completed") setParams({ status: "completed" });
              else setParams(filter === "all" ? {} : { filter });
            }}
          >
            {filter === "all" ? "All Files" : filter[0].toUpperCase() + filter.slice(1)}
          </button>
        ))}
      </div>
      <label className="label" htmlFor="history-search">Search</label>
      <input id="history-search" className="field max-w-md" value={query} onChange={(event) => { setQuery(event.target.value); setPage(0); }} placeholder="Search file name" />
      {error ? <p className="mt-4 text-sm text-[var(--danger)]">{error}</p> : null}
      <div className="mt-4">
        {filtered.length === 0 ? (
          <EmptyState title="No files analyzed yet." body="Completed, failed, and suspicious filters only match investigations that already exist." action={<Link className="btn btn-primary" to="/app/analyze">New Analysis</Link>} />
        ) : (
          <div className="overflow-x-auto">
            <JobTable jobs={visible} />
            <div className="mt-3 flex flex-wrap gap-3 text-sm">
              {visible.map((job) => (
                <span key={job.job_id} className="inline-flex gap-3">
                  <button type="button" className="text-[var(--danger)]" onClick={() => setPending(job)}>Delete Analysis</button>
                </span>
              ))}
            </div>
            <div className="mt-4 flex items-center gap-3 text-sm">
              <button type="button" className="btn btn-secondary" disabled={page === 0} onClick={() => setPage((value) => value - 1)}>Previous</button>
              <span className="muted">Page {page + 1} of {pages}</span>
              <button type="button" className="btn btn-secondary" disabled={page + 1 >= pages} onClick={() => setPage((value) => value + 1)}>Next</button>
            </div>
          </div>
        )}
      </div>
      {pending ? (
        <Dialog
          title="Delete Analysis"
          body={`Delete ${pending.file_name} and its stored report? This does not change any other account.`}
          confirmLabel="Delete Analysis"
          onCancel={() => setPending(null)}
          onConfirm={() => {
            void deleteJob(pending.job_id)
              .then(() => {
                push("The analysis was deleted.");
                setPending(null);
                return load();
              })
              .catch((reason) => push(errorMessage(reason, "The analysis could not be deleted."), "danger"));
          }}
        />
      ) : null}
    </AppShell>
  );
}
