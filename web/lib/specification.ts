import { apiOrigin } from "@/lib/projects"
import type { Job } from "@/lib/jobs"

export type DemandMode = "autonome" | "valide"

export type Block = { name: string; role: string }

export type Rail = { name: string; voltage_v: number; current_a: number }

export type BoardSpecification = {
  name: string
  blocks: Block[]
  rails: Rail[]
  interfaces: string[]
  dimensions: { max_width_mm: number; max_height_mm: number }
  layers: 1 | 2 | 4
  budget: { max_amount: number; currency: string }
  mode: DemandMode
  assumptions: string[]
}

export type SpecificationView =
  | { state: "absente" }
  | { state: "questions"; questions: string[] }
  | { state: "refusee"; explanation: string }
  | { state: "prete"; specification: BoardSpecification }

export type ConversationMessage = {
  role: "maker" | "agent"
  content: string
}

export type Conversation = { messages: ConversationMessage[] }

export async function readSpecification(
  projectId: string
): Promise<SpecificationView> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/specification`,
    { cache: "no-store" }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible de lire la spécification."))
  }
  return response.json()
}

export async function readConversation(
  projectId: string
): Promise<Conversation> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/conversation`,
    { cache: "no-store" }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible de lire la conversation."))
  }
  return response.json()
}

export async function sendDemand(
  projectId: string,
  text: string,
  mode: DemandMode
): Promise<Job> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/demandes`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text, mode }),
    }
  )
  if (!response.ok) {
    throw new Error(await readError(response, "Impossible d'envoyer la demande."))
  }
  return response.json()
}

export async function saveSpecification(
  projectId: string,
  specification: BoardSpecification
): Promise<SpecificationView> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/specification`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(specification),
    }
  )
  if (!response.ok) {
    throw new Error(
      await readError(response, "Impossible d'enregistrer la spécification.")
    )
  }
  return response.json()
}

export async function waitForJob(projectId: string, jobId: string): Promise<Job> {
  for (let attempt = 0; attempt < 70; attempt += 1) {
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
    await new Promise((resolve) => setTimeout(resolve, 1000))
  }
  throw new Error("La demande prend trop de temps.")
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
