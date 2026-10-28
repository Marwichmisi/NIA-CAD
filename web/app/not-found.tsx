import Link from "next/link"

import { buttonVariants } from "@/components/ui/button"
import { cn } from "@/lib/utils"

export default function NotFound() {
  return (
    <main className="mx-auto flex min-h-svh w-full max-w-3xl flex-col gap-6 px-6 py-8">
      <h1 className="text-2xl font-semibold tracking-tight">
        Ce projet n&apos;existe pas.
      </h1>
      <Link
        href="/"
        className={cn(buttonVariants({ variant: "link" }), "w-fit")}
      >
        Retour aux projets
      </Link>
    </main>
  )
}
