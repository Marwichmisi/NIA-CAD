import { connection } from "next/server"
import { notFound } from "next/navigation"

import { Workspace } from "@/components/workspace"
import { openProject } from "@/lib/projects"

export const dynamic = "force-dynamic"

export default async function ProjectPage({
  params,
}: {
  params: Promise<{ id: string }>
}) {
  await connection()
  const { id } = await params
  const project = await openProject(id)
  if (!project) {
    notFound()
  }
  return <Workspace project={project} />
}
