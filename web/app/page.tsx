import { connection } from "next/server"

import { ProjectHome } from "@/components/project-home"
import { listProjects } from "@/lib/projects"

export const dynamic = "force-dynamic"

export default async function Page() {
  await connection()
  const projects = await listProjects().catch(() => null)
  if (!projects) {
    return (
      <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-4 px-6 py-8">
        <h1 className="text-2xl font-semibold tracking-tight">NIA PCB</h1>
        <p>Impossible de lire les projets. Relance l&apos;application.</p>
      </main>
    )
  }
  return <ProjectHome projects={projects} />
}
