import { apiOrigin } from "@/lib/projects"
import type { Job } from "@/lib/jobs"

export type AtoView = {
  project_id: string
  existe: boolean
  code: string
  version: number
  mis_a_jour_le: string | null
  layout_a_jour: boolean
}

export type BomView = {
  project_id: string
  entrees: Record<string, unknown>[]
  mis_a_jour_le: string | null
}

export async function readAto(projectId: string): Promise<AtoView> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/ato`,
    { cache: "no-store" }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible de lire le .ato."))
  }
  return response.json()
}

export async function saveAto(
  projectId: string,
  code: string
): Promise<AtoView> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/ato`,
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ code }),
    }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible d'enregistrer le .ato."))
  }
  return response.json()
}

export async function readBom(projectId: string): Promise<BomView> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/ato/bom`,
    { cache: "no-store" }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible de lire la BOM."))
  }
  return response.json()
}

export async function buildAto(projectId: string): Promise<Job> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/ato/construire`,
    { method: "POST" }
  )
  if (!response.ok) {
    throw new Error(
      await readError(response, "Impossible de lancer la construction.")
    )
  }
  return response.json()
}

export async function waitForAtoJob(
  projectId: string,
  jobId: string
): Promise<Job> {
  for (let attempt = 0; attempt < 60; attempt += 1) {
    const response = await fetch(
      `${apiOrigin()}/api/projects/${projectId}/jobs/${jobId}`,
      { cache: "no-store" }
    )
    if (!response.ok) {
      throw new Error(await readError(response, "Impossible de lire le job."))
    }
    const job: Job = await response.json()
    if (job.status === "termine" || job.status === "echec" || job.status === "arrete") {
      return job
    }
    await new Promise((resolve) => setTimeout(resolve, 500))
  }
  throw new Error("La construction prend trop de temps.")
}

async function readError(response: Response, fallback: string): Promise<string> {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  if (typeof detail === "string") {
    return detail
  }
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
    return detail[0].msg.replace(/^Value error,\s*/, "")
  }
  return fallback
}
