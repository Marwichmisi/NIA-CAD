"use client"

import { FormEvent, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import type { CostsTotals } from "@/lib/costs"
import {
  resetSettings,
  updateSettings,
  type PublicSettings,
  type SettingsUpdate,
} from "@/lib/settings"

export function SettingsForm({
  initial,
  totals,
}: {
  initial: PublicSettings
  totals: CostsTotals | null
}) {
  const [values, setValues] = useState<SettingsUpdate>({
    llm_model: initial.llm_model,
    llm_base_url: initial.llm_base_url,
    ato_max_iterations: initial.ato_max_iterations,
    routing_max_passes: initial.routing_max_passes,
    retention_builds_days: initial.retention_builds_days,
    retention_abandoned_days: initial.retention_abandoned_days,
    project_token_budget: initial.project_token_budget,
    project_cost_budget_eur: initial.project_cost_budget_eur,
  })
  const [keys, setKeys] = useState({
    has_llm_key: initial.has_llm_key,
    has_jlcpcb_key: initial.has_jlcpcb_key,
  })
  const [budgets, setBudgets] = useState({
    project_token_budget: initial.project_token_budget,
    project_cost_budget_eur: initial.project_cost_budget_eur,
  })
  const [error, setError] = useState<string | null>(null)
  const [saved, setSaved] = useState(false)
  const [pending, setPending] = useState(false)

  function set<K extends keyof SettingsUpdate>(key: K, value: SettingsUpdate[K]) {
    setValues((current) => ({ ...current, [key]: value }))
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    setPending(true)
    setError(null)
    setSaved(false)
    const result = await updateSettings(values)
    if (!result.ok) {
      setError(result.message)
      setPending(false)
      return
    }
    setKeys({
      has_llm_key: result.settings.has_llm_key,
      has_jlcpcb_key: result.settings.has_jlcpcb_key,
    })
    setBudgets({
      project_token_budget: result.settings.project_token_budget,
      project_cost_budget_eur: result.settings.project_cost_budget_eur,
    })
    setSaved(true)
    setPending(false)
  }

  async function onReset() {
    setPending(true)
    setError(null)
    const next = await resetSettings()
    if (!next) {
      setError("La remise par défaut a échoué.")
      setPending(false)
      return
    }
    setValues({
      llm_model: next.llm_model,
      llm_base_url: next.llm_base_url,
      ato_max_iterations: next.ato_max_iterations,
      routing_max_passes: next.routing_max_passes,
      retention_builds_days: next.retention_builds_days,
      retention_abandoned_days: next.retention_abandoned_days,
      project_token_budget: next.project_token_budget,
      project_cost_budget_eur: next.project_cost_budget_eur,
    })
    setKeys({
      has_llm_key: next.has_llm_key,
      has_jlcpcb_key: next.has_jlcpcb_key,
    })
    setBudgets({
      project_token_budget: next.project_token_budget,
      project_cost_budget_eur: next.project_cost_budget_eur,
    })
    setSaved(true)
    setPending(false)
  }

  return (
    <div className="flex flex-col gap-8">
      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Secrets</h2>
        <p className="text-sm text-muted-foreground">
          Les clés restent dans l&apos;environnement local et ne sont jamais
          affichées.
        </p>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-sm">Clé LLM</span>
          <Badge variant={keys.has_llm_key ? "secondary" : "outline"}>
            {keys.has_llm_key ? "Configurée" : "Absente"}
          </Badge>
          <span className="text-sm">Clé JLCPCB</span>
          <Badge variant={keys.has_jlcpcb_key ? "secondary" : "outline"}>
            {keys.has_jlcpcb_key ? "Configurée" : "Absente"}
          </Badge>
        </div>
      </section>

      <Separator />

      <form onSubmit={onSubmit}>
        <FieldGroup>
          <Field>
            <FieldLabel htmlFor="llm_model">Modèle LLM</FieldLabel>
            <Input
              id="llm_model"
              value={values.llm_model}
              maxLength={80}
              autoComplete="off"
              disabled={pending}
              onChange={(event) => set("llm_model", event.target.value)}
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="llm_base_url">URL de base LLM</FieldLabel>
            <Input
              id="llm_base_url"
              value={values.llm_base_url}
              maxLength={200}
              autoComplete="off"
              disabled={pending}
              onChange={(event) => set("llm_base_url", event.target.value)}
            />
            <FieldDescription>
              Synchronisée avec la configuration déclarative.
            </FieldDescription>
          </Field>
          <Field>
            <FieldLabel htmlFor="ato_max_iterations">
              Boucles .ato (défaut 30)
            </FieldLabel>
            <Input
              id="ato_max_iterations"
              type="number"
              min={1}
              value={values.ato_max_iterations}
              disabled={pending}
              onChange={(event) =>
                set("ato_max_iterations", Number(event.target.value))
              }
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="routing_max_passes">
              Passes de routage (défaut 15)
            </FieldLabel>
            <Input
              id="routing_max_passes"
              type="number"
              min={1}
              value={values.routing_max_passes}
              disabled={pending}
              onChange={(event) =>
                set("routing_max_passes", Number(event.target.value))
              }
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="retention_builds_days">
              Rétention builds (jours)
            </FieldLabel>
            <Input
              id="retention_builds_days"
              type="number"
              min={1}
              value={values.retention_builds_days}
              disabled={pending}
              onChange={(event) =>
                set("retention_builds_days", Number(event.target.value))
              }
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="retention_abandoned_days">
              Rétention projets abandonnés (jours)
            </FieldLabel>
            <Input
              id="retention_abandoned_days"
              type="number"
              min={1}
              value={values.retention_abandoned_days}
              disabled={pending}
              onChange={(event) =>
                set("retention_abandoned_days", Number(event.target.value))
              }
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="project_token_budget">
              Budget jetons par projet
            </FieldLabel>
            <Input
              id="project_token_budget"
              type="number"
              min={1}
              value={values.project_token_budget}
              disabled={pending}
              onChange={(event) =>
                set("project_token_budget", Number(event.target.value))
              }
            />
          </Field>
          <Field>
            <FieldLabel htmlFor="project_cost_budget_eur">
              Budget coût par projet (EUR)
            </FieldLabel>
            <Input
              id="project_cost_budget_eur"
              type="number"
              min={0}
              step="0.01"
              value={values.project_cost_budget_eur}
              disabled={pending}
              onChange={(event) =>
                set("project_cost_budget_eur", Number(event.target.value))
              }
            />
            <FieldDescription>
              Alerte à 80 %, blocage au plafond sauf dépassement manuel
              journalisé.
            </FieldDescription>
          </Field>
          <Field data-invalid={error ? true : undefined}>
            <FieldError>{error}</FieldError>
            {saved ? (
              <p className="text-sm text-muted-foreground">
                Réglages enregistrés.
              </p>
            ) : null}
          </Field>
          <div className="flex flex-wrap gap-2">
            <Button type="submit" disabled={pending}>
              {pending ? "Enregistrement…" : "Enregistrer"}
            </Button>
            <Button type="button" variant="outline" disabled={pending} onClick={onReset}>
              Remettre par défaut
            </Button>
          </div>
        </FieldGroup>
      </form>

      <Separator />

      <section className="flex flex-col gap-3">
        <h2 className="text-lg font-medium">Coûts</h2>
        {totals ? (
          <div className="flex flex-col gap-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Cumul</span>
              <Badge variant="outline">
                {totals.total_tokens} jetons · {totals.total_cost.toFixed(2)} EUR
              </Badge>
            </div>
            {totals.projects.length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Aucun coût enregistré.
              </p>
            ) : (
              <ul className="flex flex-col gap-2">
                {totals.projects.map((item) => (
                  <li
                    key={item.project_id}
                    className="flex flex-wrap items-center gap-2"
                  >
                    <span className="text-sm font-medium">
                      {item.project_name || item.project_id}
                    </span>
                    <Badge variant="secondary">
                      {item.tokens} jetons · {item.cost.toFixed(2)} EUR
                    </Badge>
                    {item.tokens >= budgets.project_token_budget ||
                    item.cost >= budgets.project_cost_budget_eur ? (
                      <Badge variant="destructive">Plafond atteint</Badge>
                    ) : item.tokens >= 0.8 * budgets.project_token_budget ||
                      item.cost >= 0.8 * budgets.project_cost_budget_eur ? (
                      <Badge variant="outline">Alerte 80 %</Badge>
                    ) : null}
                  </li>
                ))}
              </ul>
            )}
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">
            Impossible de lire les coûts.
          </p>
        )}
      </section>
    </div>
  )
}
