import { apiOrigin } from "@/lib/projects"

/** Un job tel que l'API le renvoie. */
export type JobStatus =
  | "en_attente"
  | "en_cours"
  | "arrete"
  | "termine"
  | "echec"

export type Job = {
  id: string
  project_id: string
  step: string
  status: JobStatus
  checkpoint: string | null
  progress: { done: number; total: number } | null
  journal: string[]
  error: string | null
}

export const JOB_STATUS_LABEL: Record<JobStatus, string> = {
  en_attente: "En attente",
  en_cours: "En cours",
  arrete: "Arrêté",
  termine: "Terminé",
  echec: "Échec",
}

export async function latestJob(projectId: string): Promise<Job | null> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/jobs/latest`,
    { cache: "no-store" }
  )
  if (response.status === 404) {
    const detail = await readError(response)
    if (detail === "Ce projet n'a pas de job.") {
      return null
    }
    throw new Error(detail)
  }
  if (!response.ok) {
    throw new Error("Impossible de lire le job.")
  }
  return response.json()
}

export async function stopJob(projectId: string, jobId: string): Promise<Job> {
  return postJob(projectId, jobId, "stop")
}

export async function resumeJob(
  projectId: string,
  jobId: string
): Promise<Job> {
  return postJob(projectId, jobId, "resume")
}

async function postJob(
  projectId: string,
  jobId: string,
  action: "stop" | "resume"
): Promise<Job> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/jobs/${jobId}/${action}`,
    { method: "POST" }
  )
  if (!response.ok) {
    throw new Error(await readError(response))
  }
  return response.json()
}

async function readError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  if (typeof detail === "string") {
    return detail
  }
  return "Le job n'a pas pu être mis à jour."
}
