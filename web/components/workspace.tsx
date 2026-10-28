import Link from "next/link"

import { JobJournal } from "@/components/job-journal"
import { PreviewPanel } from "@/components/preview-panel"
import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"
import {
  Field,
  FieldDescription,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Marker, MarkerContent } from "@/components/ui/marker"
import {
  MessageScroller,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import { formatProjectDate, type Project } from "@/lib/projects"
import type { Job } from "@/lib/jobs"

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
}: {
  project: Project
  job: Job | null
}) {
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
              <span className="text-sm text-muted-foreground">En attente</span>
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
        <MessageScrollerProvider>
          <MessageScroller className="min-h-40 flex-1">
            <MessageScrollerViewport>
              <MessageScrollerContent>
                <MessageScrollerItem messageId="aucun-message">
                  <Marker>
                    <MarkerContent>Aucun message.</MarkerContent>
                  </Marker>
                </MessageScrollerItem>
              </MessageScrollerContent>
            </MessageScrollerViewport>
          </MessageScroller>
        </MessageScrollerProvider>
        <form className="flex flex-col gap-3 border-t p-4">
          <Field data-disabled>
            <FieldLabel htmlFor="chat-message">Message</FieldLabel>
            <Input
              id="chat-message"
              disabled
              placeholder="Décris la carte"
            />
            <FieldDescription>
              L&apos;envoi n&apos;est pas encore disponible.
            </FieldDescription>
          </Field>
          <Button type="button" disabled>
            Envoyer
          </Button>
        </form>
      </aside>
    </div>
  )
}
