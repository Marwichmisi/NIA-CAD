import Link from "next/link"

import { SettingsForm } from "@/components/settings-form"
import { buttonVariants } from "@/components/ui/button"
import { readTotals } from "@/lib/costs"
import { readSettings } from "@/lib/settings"
import { cn } from "@/lib/utils"

export const dynamic = "force-dynamic"

export default async function SettingsPage() {
  const [settings, totals] = await Promise.all([
    readSettings(),
    readTotals(),
  ])
  if (!settings) {
    return (
      <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-6 px-6 py-8">
        <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
        <p className="max-w-prose text-muted-foreground">
          Impossible de lire les réglages. Relance l&apos;application.
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
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-6 px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">Réglages</h1>
      <SettingsForm initial={settings} totals={totals} />
      <Link href="/" className={cn(buttonVariants({ variant: "link" }), "w-fit")}>
        Retour aux projets
      </Link>
    </main>
  )
}
