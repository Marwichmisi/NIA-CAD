"use client"

import { useEffect, useState } from "react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import { buildAto, readAto, readBom, saveAto, waitForAtoJob, type BomView } from "@/lib/ato"

const PANES = [
  { value: "carte", label: "Carte" },
  { value: "schema", label: "Schéma" },
  { value: "ato", label: "Code .ato" },
  { value: "bom", label: "BOM" },
] as const

type Pane = (typeof PANES)[number]["value"]
type BoardView = "2d" | "3d"

export function PreviewPanel({ projectId }: { projectId: string }) {
  const [pane, setPane] = useState<Pane>("carte")
  const [view, setView] = useState<BoardView>("2d")
  const [code, setCode] = useState("")
  const [version, setVersion] = useState(0)
  const [bom, setBom] = useState<BomView | null>(null)
  const [busy, setBusy] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [ato, nomenclature] = await Promise.all([
          readAto(projectId),
          readBom(projectId),
        ])
        if (!cancelled) {
          setCode(ato.code)
          setVersion(ato.version)
          setBom(nomenclature)
        }
      } catch (error) {
        if (!cancelled) {
          setMessage(
            error instanceof Error ? error.message : "Lecture impossible."
          )
        }
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [projectId])

  async function onSave() {
    setBusy(true)
    setMessage(null)
    try {
      const next = await saveAto(projectId, code)
      setVersion(next.version)
      setMessage(`Version ${next.version} enregistrée localement.`)
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Enregistrement impossible.")
    } finally {
      setBusy(false)
    }
  }

  async function onBuild() {
    setBusy(true)
    setMessage(null)
    try {
      if (code.trim()) {
        const saved = await saveAto(projectId, code)
        setVersion(saved.version)
        setCode(saved.code)
      }
      const launched = await buildAto(projectId)
      setMessage("Construction lancée : suis le journal sous l'aperçu.")
      const finished = await waitForAtoJob(projectId, launched.id)
      const [ato, nomenclature] = await Promise.all([
        readAto(projectId),
        readBom(projectId),
      ])
      setCode(ato.code)
      setVersion(ato.version)
      setBom(nomenclature)
      setMessage(
        finished.status === "echec"
          ? (finished.error ?? "La construction a échoué.")
          : `Construction rapide : BOM ${nomenclature.entrees.length} ligne(s), layout à jour.`
      )
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Construction impossible.")
    } finally {
      setBusy(false)
    }
  }

  return (
    <section className="flex min-h-96 flex-col gap-3 p-4 [grid-area:preview] lg:min-h-0">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <h2 className="text-sm font-medium">Aperçu</h2>
        <ToggleGroup
          value={[view]}
          onValueChange={(next) => {
            const selected = next[0]
            if (selected === "2d" || selected === "3d") {
              setView(selected)
              setPane("carte")
            }
          }}
        >
          <ToggleGroupItem value="2d">2D</ToggleGroupItem>
          <ToggleGroupItem value="3d">3D</ToggleGroupItem>
        </ToggleGroup>
      </div>
      <Tabs
        value={pane}
        onValueChange={(value) => {
          if (value === "carte" || value === "schema" || value === "ato" || value === "bom") {
            setPane(value)
          }
        }}
        className="min-h-0 flex-1"
      >
        <TabsList>
          {PANES.map((item) => (
            <TabsTrigger key={item.value} value={item.value}>
              {item.label}
            </TabsTrigger>
          ))}
        </TabsList>
        <TabsContent value="carte" className="min-h-64 flex-1">
          {view === "2d" ? (
            <div className="board-grid flex h-full min-h-64 items-center justify-center">
              <Empty>
                <EmptyHeader>
                  <EmptyTitle>Pas de carte</EmptyTitle>
                  <EmptyDescription>
                    Le cuivre apparaîtra ici, couche par couche.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
            </div>
          ) : (
            <Empty className="h-full min-h-64">
              <EmptyHeader>
                <EmptyTitle>Pas de modèle 3D</EmptyTitle>
                <EmptyDescription>
                  Le volume de la carte s&apos;affichera après la construction.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </TabsContent>
        <TabsContent value="schema" className="min-h-64 flex-1">
          <Empty className="h-full min-h-64">
            <EmptyHeader>
              <EmptyTitle>Pas de schéma</EmptyTitle>
            </EmptyHeader>
          </Empty>
        </TabsContent>
        <TabsContent value="ato" className="min-h-64 flex-1">
          <div className="flex h-full min-h-64 flex-col gap-3">
            <div className="flex flex-wrap items-center gap-3">
              <p className="text-sm text-muted-foreground">
                {version > 0 ? `Version ${version}` : "Aucune version"}
              </p>
              <button
                type="button"
                disabled={busy}
                onClick={() => void onSave()}
                className="text-sm underline"
              >
                Enregistrer
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => void onBuild()}
                className="text-sm underline"
              >
                Construire
              </button>
            </div>
            {message ? <p className="text-sm">{message}</p> : null}
            <textarea
              aria-label="Code .ato"
              value={code}
              onChange={(event) => setCode(event.target.value)}
              spellCheck={false}
              className="min-h-64 flex-1 font-mono text-sm"
              placeholder="Le code .ato apparaîtra ici."
            />
          </div>
        </TabsContent>
        <TabsContent value="bom" className="min-h-64 flex-1">
          {bom && bom.entrees.length > 0 ? (
            <ul className="flex flex-col gap-2">
              {bom.entrees.map((entry, index) => (
                <li key={index} className="text-sm">
                  {JSON.stringify(entry)}
                </li>
              ))}
            </ul>
          ) : (
            <Empty className="h-full min-h-64">
              <EmptyHeader>
                <EmptyTitle>Pas de nomenclature</EmptyTitle>
                <EmptyDescription>
                  Lance une construction rapide pour générer la BOM.
                </EmptyDescription>
              </EmptyHeader>
            </Empty>
          )}
        </TabsContent>
      </Tabs>
    </section>
  )
}
