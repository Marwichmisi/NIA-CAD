import { apiOrigin } from "@/lib/projects"
import type { Job } from "@/lib/jobs"

export type ApercuCouche = {
  id: string
  label: string
  svg: string
}

export type ApercuView = {
  project_id: string
  version: number
  version_courante: number
  a_jour: boolean
  layout_a_jour: boolean
  couches: ApercuCouche[]
  modele_3d_disponible: boolean
  modele_3d_url: string | null
  pieces_sans_modele_3d: string[]
  mis_a_jour_le: string | null
}

export function modele3dUrl(projectId: string): string {
  return `${apiOrigin()}/api/projects/${projectId}/apercu/modele`
}

export async function readApercu(projectId: string): Promise<ApercuView> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/apercu`,
    { cache: "no-store" }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible de lire l'aperçu."))
  }
  return response.json()
}

export async function genererApercu(projectId: string): Promise<Job> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/apercu/generer`,
    { method: "POST" }
  )
  if (!response.ok) {
    throw new Error(
      await readError(response, "Impossible de générer l'aperçu.")
    )
  }
  return response.json()
}

export async function waitForApercuJob(
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
  throw new Error("La génération de l'aperçu prend trop de temps.")
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
