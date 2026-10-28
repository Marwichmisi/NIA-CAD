import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export default function SettingsPage() {
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-6 px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
      <p className="max-w-prose text-muted-foreground">
        Aucun réglage à modifier pour l&apos;instant.
      </p>
      <Link
        href="/"
        className={cn(buttonVariants({ variant: "link" }), "w-fit")}
      >
        Retour aux projets
      </Link>
    </main>
  )
}
