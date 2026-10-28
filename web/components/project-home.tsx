"use client"

import { FormEvent, useState } from "react"
import Link from "next/link"
import { useRouter } from "next/navigation"

import { Badge } from "@/components/ui/badge"
import { Button, buttonVariants } from "@/components/ui/button"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import {
  createProject,
  formatProjectDate,
  type Project,
} from "@/lib/projects"

export function ProjectHome({ projects }: { projects: Project[] }) {
  const router = useRouter()
  const [error, setError] = useState<string | null>(null)
  const [pending, setPending] = useState(false)

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    const form = event.currentTarget
    const name = String(new FormData(form).get("name") ?? "")
    setPending(true)
    setError(null)
    const result = await createProject(name)
    if (!result.ok) {
      setError(result.message)
      setPending(false)
      return
    }
    router.push(`/projets/${result.project.id}`)
  }

  return (
    <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-10 px-6 py-8">
      <header className="flex items-center justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">NIA PCB</h1>
        <Link href="/reglages" className={buttonVariants({ variant: "link" })}>
          Réglages
        </Link>
      </header>

      <form onSubmit={onSubmit}>
        <FieldGroup>
          <Field data-invalid={error ? true : undefined}>
            <FieldLabel htmlFor="project-name">Nom du projet</FieldLabel>
            <Input
              id="project-name"
              name="name"
              required
              maxLength={80}
              autoComplete="off"
              aria-invalid={error ? true : undefined}
              disabled={pending}
            />
            <FieldError>{error}</FieldError>
          </Field>
          <Button type="submit" disabled={pending}>
            {pending ? "Création…" : "Créer le projet"}
          </Button>
        </FieldGroup>
      </form>

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Projets</h2>
        {projects.length === 0 ? (
          <Empty>
            <EmptyHeader>
              <EmptyTitle>Aucun projet</EmptyTitle>
              <EmptyDescription>
                Donne un nom pour ouvrir un plan vide.
              </EmptyDescription>
            </EmptyHeader>
          </Empty>
        ) : (
          <ul>
            {projects.map((project, index) => (
              <li key={project.id}>
                {index > 0 ? <Separator /> : null}
                <div className="flex items-center justify-between gap-4 py-3">
                  <div className="flex min-w-0 flex-col gap-1">
                    <p className="truncate font-medium">{project.name}</p>
                    <div className="flex flex-wrap items-center gap-2">
                      <Badge variant="outline">Brouillon</Badge>
                      <p className="text-sm text-muted-foreground">
                        <time
                          dateTime={project.status_changed_at}
                          suppressHydrationWarning
                        >
                          {formatProjectDate(project.status_changed_at)}
                        </time>
                      </p>
                    </div>
                  </div>
                  <Link
                    href={`/projets/${project.id}`}
                    className={buttonVariants({ variant: "outline" })}
                  >
                    Ouvrir
                  </Link>
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>
    </main>
  )
}
