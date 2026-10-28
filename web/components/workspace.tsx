"use client"

import { useState } from "react"
import Link from "next/link"

import { JobJournal } from "@/components/job-journal"
import { PreviewPanel } from "@/components/preview-panel"
import { SpecChat } from "@/components/spec-chat"
import { Badge } from "@/components/ui/badge"
import { buttonVariants } from "@/components/ui/button"
import type { Job } from "@/lib/jobs"
import { formatProjectDate, type Project } from "@/lib/projects"
import {
  type ConversationMessage,
  type SpecificationView,
} from "@/lib/specification"
import { cn } from "@/lib/utils"

const STEPS = [
  "Spécification",
  "Pièces",
  "Schéma",
  "Placement",
  "Fabrication",
]

export function Workspace({
  project,
  job,
  specification,
  conversation,
}: {
  project: Project
  job: Job | null
  specification: SpecificationView
  conversation: ConversationMessage[]
}) {
  const [currentSpecification, setCurrentSpecification] = useState(specification)
  const [messages, setMessages] = useState(conversation)

  return (
    <div className="grid min-h-svh grid-cols-1 [grid-template-areas:'header'_'steps'_'preview'_'journal'_'chat'] lg:h-svh lg:grid-cols-[14rem_minmax(0,1fr)_22rem] lg:grid-rows-[auto_minmax(0,1fr)_12rem] lg:[grid-template-areas:'header_header_header'_'steps_preview_chat'_'steps_journal_chat']">
      <header className="flex flex-wrap items-center justify-between gap-3 border-b px-4 py-3 [grid-area:header]">
        <div className="flex min-w-0 flex-wrap items-center gap-3">
          <Link href="/" className={buttonVariants({ variant: "link" })}>
            Projets
          </Link>
          <h1 className="truncate text-lg font-semibold">{project.name}</h1>
          <Badge variant="outline">Brouillon</Badge>
          <p className="text-sm text-muted-foreground">
            <time dateTime={project.status_changed_at} suppressHydrationWarning>
              {formatProjectDate(project.status_changed_at)}
            </time>
          </p>
        </div>
        <Link
          href="/reglages"
          className={cn(buttonVariants({ variant: "link" }))}
        >
          Réglages
        </Link>
      </header>

      <aside className="flex flex-col gap-4 border-b p-4 [grid-area:steps] lg:border-r lg:border-b-0">
        <h2 className="text-sm font-medium">Étapes</h2>
        <ol className="flex flex-col gap-3">
          {STEPS.map((step, index) => (
            <li key={step} className="flex items-baseline justify-between gap-3">
              <span>
                <span className="text-muted-foreground">{index + 1}. </span>
                {step}
              </span>
              <span className="text-sm text-muted-foreground">
                {index === 0
                  ? specificationLabel(currentSpecification)
                  : "En attente"}
              </span>
            </li>
          ))}
        </ol>
      </aside>

      <PreviewPanel />

      <section className="flex min-h-0 flex-col gap-3 border-t p-4 [grid-area:journal]">
        <h2 className="text-sm font-medium">Journal</h2>
        <JobJournal projectId={project.id} initialJob={job} />
      </section>

      <aside className="flex min-h-80 flex-col border-t [grid-area:chat] lg:min-h-0 lg:border-t-0 lg:border-l">
        <h2 className="px-4 pt-4 text-sm font-medium">Chat</h2>
        <SpecChat
          projectId={project.id}
          conversation={messages}
          specification={currentSpecification}
          onConversation={setMessages}
          onSpecification={setCurrentSpecification}
        />
      </aside>
    </div>
  )
}

function specificationLabel(specification: SpecificationView): string {
  if (specification.state === "prete") {
    return "Prête"
  }
  if (specification.state === "questions") {
    return "Questions"
  }
  if (specification.state === "refusee") {
    return "Refusée"
  }
  return "En attente"
}
