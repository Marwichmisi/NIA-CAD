import { apiOrigin } from "@/lib/projects"

export type PublicSettings = {
  llm_model: string
  llm_base_url: string
  ato_max_iterations: number
  routing_max_passes: number
  retention_builds_days: number
  retention_abandoned_days: number
  project_token_budget: number
  project_cost_budget_eur: number
  has_llm_key: boolean
  has_jlcpcb_key: boolean
}

export type SettingsUpdate = Omit<PublicSettings, "has_llm_key" | "has_jlcpcb_key">

export async function readSettings(): Promise<PublicSettings | null> {
  const response = await fetch(`${apiOrigin()}/api/settings`, {
    cache: "no-store",
  })
  if (!response.ok) {
    return null
  }
  return response.json()
}

export async function updateSettings(
  body: SettingsUpdate
): Promise<{ ok: true; settings: PublicSettings } | { ok: false; message: string }> {
  const response = await fetch(`${apiOrigin()}/api/settings`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  })
  if (response.ok) {
    return { ok: true, settings: await response.json() }
  }
  return { ok: false, message: await readError(response) }
}

export async function resetSettings(): Promise<PublicSettings | null> {
  const response = await fetch(`${apiOrigin()}/api/settings/reset`, {
    method: "POST",
  })
  if (!response.ok) {
    return null
  }
  return response.json()
}

async function readError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  if (typeof detail === "string") {
    return detail
  }
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
    return String(detail[0].msg).replace(/^Value error,\s*/, "")
  }
  return "Les réglages n'ont pas pu être enregistrés."
}
