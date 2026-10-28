import { apiOrigin } from "@/lib/projects"

export type CostSummary = {
  project_id: string
  project_tokens: number
  project_cost: number
  total_tokens: number
  total_cost: number
  token_budget: number
  cost_budget: number
  alert_80: boolean
  over_budget: boolean
}

export type CostsTotals = {
  total_tokens: number
  total_cost: number
  projects: Array<{
    project_id: string
    project_name: string
    tokens: number
    cost: number
  }>
}

export async function readProjectCosts(
  projectId: string
): Promise<CostSummary | null> {
  const response = await fetch(
    `${apiOrigin()}/api/projects/${projectId}/costs`,
    { cache: "no-store" }
  )
  if (!response.ok) {
    return null
  }
  return response.json()
}

export async function readTotals(): Promise<CostsTotals | null> {
  const response = await fetch(`${apiOrigin()}/api/costs`, {
    cache: "no-store",
  })
  if (!response.ok) {
    return null
  }
  return response.json()
}
