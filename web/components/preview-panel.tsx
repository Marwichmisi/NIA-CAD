"use client"

import { useEffect, useState } from "react"

import { Modele3D } from "@/components/modele-3d"
import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"
import {
  genererApercu,
  modele3dUrl,
  readApercu,
  waitForApercuJob,
  type ApercuView,
} from "@/lib/apercu"
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
  const [apercu, setApercu] = useState<ApercuView | null>(null)
  const [coucheId, setCoucheId] = useState("F.Cu")
  const [busy, setBusy] = useState(false)
  const [busyApercu, setBusyApercu] = useState(false)
  const [message, setMessage] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    async function load() {
      try {
        const [ato, nomenclature, ap] = await Promise.all([
          readAto(projectId),
          readBom(projectId),
          readApercu(projectId),
        ])
        if (!cancelled) {
          setCode(ato.code)
          setVersion(ato.version)
          setBom(nomenclature)
          setApercu(ap)
          if (ap.couches.length > 0) {
            setCoucheId((prev) =>
              ap.couches.some((c) => c.id === prev) ? prev : ap.couches[0].id
            )
          }
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
      if (finished.status === "echec") {
        const [ato, nomenclature, ap] = await Promise.all([
          readAto(projectId),
          readBom(projectId),
          readApercu(projectId),
        ])
        setCode(ato.code)
        setVersion(ato.version)
        setBom(nomenclature)
        setApercu(ap)
        setMessage(finished.error ?? "La construction a échoué.")
        return
      }
      const [ato, nomenclature] = await Promise.all([
        readAto(projectId),
        readBom(projectId),
      ])
      setCode(ato.code)
      setVersion(ato.version)
      setBom(nomenclature)
      // Après une construction avec layout, l'aperçu doit suivre :
      // génération best-effort, le 2D/3D existant reste sinon.
      try {
        const gen = await genererApercu(projectId)
        await waitForApercuJob(projectId, gen.id)
      } catch {
        // L'aperçu reste lisible même si KiCad est absent.
      }
      const ap = await readApercu(projectId)
      setApercu(ap)
      if (ap.couches.length > 0) {
        setCoucheId((prev) =>
          ap.couches.some((c) => c.id === prev) ? prev : ap.couches[0].id
        )
      }
      setMessage(
        `Construction rapide : BOM ${nomenclature.entrees.length} ligne(s), ` +
          `aperçu v${ap.version} (${ap.couches.length} couche(s)` +
          (ap.modele_3d_disponible ? ", modèle 3D prêt" : ", sans modèle 3D") +
          ")."
      )
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Construction impossible.")
    } finally {
      setBusy(false)
    }
  }

  async function onGenererApercu() {
    setBusyApercu(true)
    setMessage(null)
    try {
      const launched = await genererApercu(projectId)
      setMessage("Génération de l'aperçu lancée.")
      const finished = await waitForApercuJob(projectId, launched.id)
      const ap = await readApercu(projectId)
      setApercu(ap)
      if (ap.couches.length > 0) {
        setCoucheId((prev) =>
          ap.couches.some((c) => c.id === prev) ? prev : ap.couches[0].id
        )
      }
      setMessage(
        finished.status === "echec"
          ? (finished.error ?? "La génération de l'aperçu a échoué.")
          : `Aperçu v${ap.version} : ${ap.couches.length} couche(s)` +
              (ap.modele_3d_disponible ? ", modèle 3D prêt." : ", sans modèle 3D.")
      )
    } catch (error) {
      setMessage(
        error instanceof Error ? error.message : "Génération impossible."
      )
    } finally {
      setBusyApercu(false)
    }
  }

  const coucheActive =
    apercu?.couches.find((c) => c.id === coucheId) ?? apercu?.couches[0]

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
          <div className="mb-2 flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
            <span>
              {apercu
                ? `Aperçu v${apercu.version} / code v${apercu.version_courante}`
                : version > 0
                  ? `Version ${version}`
                  : "Aucune version"}
            </span>
            {apercu && !apercu.a_jour ? (
              <span className="text-amber-600">
                Obsolète — régénère après modification.
              </span>
            ) : null}
            <button
              type="button"
              disabled={busyApercu}
              onClick={() => void onGenererApercu()}
              className="text-sm underline"
            >
              Générer l&apos;aperçu
            </button>
          </div>
          {view === "2d" ? (
            apercu && apercu.couches.length > 0 && coucheActive ? (
              <div className="flex h-full min-h-64 flex-col gap-2">
                <div
                  role="tablist"
                  aria-label="Couches 2D"
                  className="flex flex-wrap gap-2"
                >
                  {apercu.couches.map((couche) => (
                    <button
                      key={couche.id}
                      type="button"
                      role="tab"
                      aria-selected={couche.id === coucheActive.id}
                      onClick={() => setCoucheId(couche.id)}
                      className="text-sm underline"
                    >
                      {couche.label}
                    </button>
                  ))}
                </div>
                <div
                  data-testid={`couche-${coucheActive.id}`}
                  className="board-grid flex h-full min-h-64 items-center justify-center overflow-auto"
                  // Le SVG vient du backend (kicad-cli) : affichage direct.
                  dangerouslySetInnerHTML={{ __html: coucheActive.svg }}
                />
                {apercu.pieces_sans_modele_3d.length > 0 ? (
                  <p className="text-sm text-amber-600">
                    Pièces sans modèle 3D :{" "}
                    {apercu.pieces_sans_modele_3d.join(", ")}
                  </p>
                ) : null}
              </div>
            ) : (
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
            )
          ) : apercu?.modele_3d_disponible && apercu.modele_3d_url ? (
            <div className="flex h-full min-h-64 flex-col gap-2">
              <Modele3D url={modele3dUrl(projectId)} />
              {apercu.pieces_sans_modele_3d.length > 0 ? (
                <p className="text-sm text-amber-600">
                  Pièces sans modèle 3D :{" "}
                  {apercu.pieces_sans_modele_3d.join(", ")}
                </p>
              ) : null}
            </div>
          ) : (
            <div className="flex h-full min-h-64 flex-col items-center justify-center gap-2">
              <Empty className="h-full min-h-64">
                <EmptyHeader>
                  <EmptyTitle>Pas de modèle 3D</EmptyTitle>
                  <EmptyDescription>
                    Le volume de la carte s&apos;affichera après la construction.
                  </EmptyDescription>
                </EmptyHeader>
              </Empty>
              {apercu && apercu.pieces_sans_modele_3d.length > 0 ? (
                <p className="text-sm text-amber-600">
                  Pièces sans modèle 3D :{" "}
                  {apercu.pieces_sans_modele_3d.join(", ")}
                </p>
              ) : null}
            </div>
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
