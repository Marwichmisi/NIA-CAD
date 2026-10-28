"use client"

import { useEffect, useState } from "react"

import { Button } from "@/components/ui/button"
import { Marker, MarkerContent } from "@/components/ui/marker"
import {
  JOB_STATUS_LABEL,
  latestJob,
  resumeJob,
  stopJob,
  type Job,
} from "@/lib/jobs"

export function JobJournal({
  projectId,
  initialJob,
}: {
  projectId: string
  initialJob: Job | null
}) {
  const [job, setJob] = useState(initialJob)
  const [pending, setPending] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false

    async function refresh() {
      try {
        const next = await latestJob(projectId)
        if (!cancelled) {
          setJob(next)
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error
              ? error.message
              : "Le journal est indisponible."
          )
        }
      }
    }

    void refresh()
    const timer = window.setInterval(() => void refresh(), 1000)
    return () => {
      cancelled = true
      window.clearInterval(timer)
    }
  }, [projectId])

  const live = job?.status === "en_cours" || job?.status === "en_attente"
  const jobId = job?.id

  useEffect(() => {
    if (!live || !jobId) {
      return
    }
    const source = new EventSource(
      `/api/projects/${projectId}/jobs/${jobId}/events`
    )
    const onLiveEvent = () => {
      void latestJob(projectId)
        .then((next) => setJob(next))
        .catch((error: unknown) => {
          setMessage(
            error instanceof Error
              ? error.message
              : "Le journal est indisponible."
          )
        })
    }
    source.addEventListener("journal", onLiveEvent)
    source.addEventListener("progression", onLiveEvent)
    source.onerror = () => {
      source.close()
    }
    return () => source.close()
  }, [projectId, jobId, live])

  async function run(action: "stop" | "resume") {
    if (!job) {
      return
    }
    setPending(true)
    setMessage(null)
    try {
      const next =
        action === "stop"
          ? await stopJob(projectId, job.id)
          : await resumeJob(projectId, job.id)
      setJob(next)
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Action impossible."
      )
    } finally {
      setPending(false)
    }
  }

  if (!job) {
    return (
      <Marker>
        <MarkerContent>Aucune action.</MarkerContent>
      </Marker>
    )
  }

  const canStop = job.status === "en_attente" || job.status === "en_cours"
  const canResume = job.status === "arrete"

  return (
    <div className="flex min-h-0 flex-1 flex-col gap-3">
      <div className="flex flex-wrap items-center gap-3">
        <p className="text-sm text-muted-foreground">
          {JOB_STATUS_LABEL[job.status]}
          {job.progress
            ? ` · ${job.progress.done} / ${job.progress.total}`
            : ""}
        </p>
        {canStop ? (
          <Button
            type="button"
            variant="outline"
            disabled={pending}
            onClick={() => void run("stop")}
          >
            Arrêter
          </Button>
        ) : null}
        {canResume ? (
          <Button
            type="button"
            disabled={pending}
            onClick={() => void run("resume")}
          >
            Reprendre
          </Button>
        ) : null}
      </div>
      {job.error ? <p className="text-sm text-destructive">{job.error}</p> : null}
      {message ? <p className="text-sm text-destructive">{message}</p> : null}
      <div
        className="flex min-h-0 flex-1 flex-col gap-2 overflow-y-auto"
        aria-live="polite"
      >
        {job.journal.length === 0 ? (
          <Marker>
            <MarkerContent>Aucune action.</MarkerContent>
          </Marker>
        ) : (
          job.journal.map((line, index) => (
            <p key={`${job.id}-${index}`} className="text-sm">
              {line}
            </p>
          ))
        )}
      </div>
    </div>
  )
}
