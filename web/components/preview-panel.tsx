"use client"

import { useState } from "react"

import {
  Empty,
  EmptyDescription,
  EmptyHeader,
  EmptyTitle,
} from "@/components/ui/empty"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { ToggleGroup, ToggleGroupItem } from "@/components/ui/toggle-group"

const PANES = [
  { value: "carte", label: "Carte" },
  { value: "schema", label: "Schéma" },
  { value: "ato", label: "Code .ato" },
  { value: "bom", label: "BOM" },
] as const

type Pane = (typeof PANES)[number]["value"]
type BoardView = "2d" | "3d"

export function PreviewPanel() {
  const [pane, setPane] = useState<Pane>("carte")
  const [view, setView] = useState<BoardView>("2d")

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
          <Empty className="h-full min-h-64">
            <EmptyHeader>
              <EmptyTitle>Pas de code .ato</EmptyTitle>
            </EmptyHeader>
          </Empty>
        </TabsContent>
        <TabsContent value="bom" className="min-h-64 flex-1">
          <Empty className="h-full min-h-64">
            <EmptyHeader>
              <EmptyTitle>Pas de nomenclature</EmptyTitle>
            </EmptyHeader>
          </Empty>
        </TabsContent>
      </Tabs>
    </section>
  )
}
