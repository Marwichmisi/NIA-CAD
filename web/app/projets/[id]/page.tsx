import { connection } from "next/server"
import { notFound } from "next/navigation"

import { Workspace } from "@/components/workspace"
import { latestJob } from "@/lib/jobs"
import { openProject } from "@/lib/projects"
import { readConversation, readSpecification } from "@/lib/specification"

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
  const [job, specification, conversation] = await Promise.all([
    latestJob(id),
    readSpecification(id),
    readConversation(id),
  ])
  return (
    <Workspace
      project={project}
      job={job}
      specification={specification}
      conversation={conversation.messages}
    />
  )
}
