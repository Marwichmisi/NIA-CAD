/** Un projet tel que l'API le renvoie. Le statut de départ est toujours brouillon. */
export type Project = {
  id: string
  name: string
  status: "brouillon"
  created_at: string
  status_changed_at: string
}

export type CreateProjectResult =
  | { ok: true; project: Project }
  | { ok: false; message: string }

function apiOrigin(): string {
  if (typeof window === "undefined") {
    return process.env.API_URL ?? "http://127.0.0.1:8000"
  }
  return ""
}

export function formatProjectDate(value: string): string {
  return new Intl.DateTimeFormat("fr-FR", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value))
}

export async function listProjects(): Promise<Project[]> {
  const response = await fetch(`${apiOrigin()}/api/projects`, {
    cache: "no-store",
  })
  if (!response.ok) {
    throw new Error("Impossible de lister les projets.")
  }
  return response.json()
}

export async function openProject(id: string): Promise<Project | null> {
  const response = await fetch(`${apiOrigin()}/api/projects/${id}`, {
    cache: "no-store",
  })
  if (response.status === 404) {
    return null
  }
  if (!response.ok) {
    throw new Error("Impossible de rouvrir le projet.")
  }
  return response.json()
}

export async function createProject(name: string): Promise<CreateProjectResult> {
  const response = await fetch(`${apiOrigin()}/api/projects`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name }),
  })
  if (response.status === 201) {
    return { ok: true, project: await response.json() }
  }
  return { ok: false, message: await readError(response) }
}

async function readError(response: Response): Promise<string> {
  const body = await response.json().catch(() => null)
  const detail = body?.detail
  if (typeof detail === "string") {
    return detail
  }
  if (Array.isArray(detail) && typeof detail[0]?.msg === "string") {
    return detail[0].msg.replace(/^Value error,\s*/, "")
  }
  return "Impossible de créer le projet."
}
