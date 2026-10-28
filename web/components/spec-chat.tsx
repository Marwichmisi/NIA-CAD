"use client"

import { useState, type Dispatch, type FormEvent, type SetStateAction } from "react"

import { Button } from "@/components/ui/button"
import { Bubble, BubbleContent } from "@/components/ui/bubble"
import { Field, FieldDescription, FieldLabel } from "@/components/ui/field"
import { Input } from "@/components/ui/input"
import { Marker, MarkerContent } from "@/components/ui/marker"
import { Message } from "@/components/ui/message"
import {
  MessageScroller,
  MessageScrollerContent,
  MessageScrollerItem,
  MessageScrollerProvider,
  MessageScrollerViewport,
} from "@/components/ui/message-scroller"
import {
  readConversation,
  readSpecification,
  saveSpecification,
  sendDemand,
  waitForJob,
  type BoardSpecification,
  type ConversationMessage,
  type DemandMode,
  type SpecificationView,
} from "@/lib/specification"

export function SpecChat({
  projectId,
  conversation,
  specification,
  onConversation,
  onSpecification,
}: {
  projectId: string
  conversation: ConversationMessage[]
  specification: SpecificationView
  onConversation: (messages: ConversationMessage[]) => void
  onSpecification: (specification: SpecificationView) => void
}) {
  const [text, setText] = useState("")
  const [mode, setMode] = useState<DemandMode>(initialMode(specification))
  const [seenSpecification, setSeenSpecification] = useState(specification)
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  if (specification !== seenSpecification) {
    setSeenSpecification(specification)
    setMode(initialMode(specification))
  }

  async function send() {
    const demand = text.trim()
    if (!demand || pending) {
      return
    }
    setPending(true)
    setError(null)
    try {
      const job = await sendDemand(projectId, demand, mode)
      const finished = await waitForJob(projectId, job.id)
      const [nextConversation, nextSpecification] = await Promise.all([
        readConversation(projectId),
        readSpecification(projectId),
      ])
      onConversation(nextConversation.messages)
      onSpecification(nextSpecification)
      setText("")
      if (finished.status === "echec") {
        setError(finished.error ?? "La demande a échoué.")
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "La demande a échoué.")
    } finally {
      setPending(false)
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void send()
  }

  return (
    <div className="flex min-h-0 flex-1 flex-col">
      <SpecStatus
        projectId={projectId}
        specification={specification}
        onSpecification={onSpecification}
      />
      <MessageScrollerProvider>
        <MessageScroller className="min-h-40 flex-1">
          <MessageScrollerViewport>
            <MessageScrollerContent>
              {conversation.length === 0 ? (
                <MessageScrollerItem messageId="aucun-message">
                  <Marker>
                    <MarkerContent>Aucun message.</MarkerContent>
                  </Marker>
                </MessageScrollerItem>
              ) : (
                conversation.map((message, index) => (
                  <MessageScrollerItem
                    key={`${message.role}-${index}`}
                    messageId={`${index}`}
                  >
                    <Message align={message.role === "maker" ? "end" : "start"}>
                      <Bubble
                        align={message.role === "maker" ? "end" : "start"}
                        variant={message.role === "maker" ? "default" : "muted"}
                      >
                        <BubbleContent className="whitespace-pre-wrap">
                          {message.content}
                        </BubbleContent>
                      </Bubble>
                    </Message>
                  </MessageScrollerItem>
                ))
              )}
            </MessageScrollerContent>
          </MessageScrollerViewport>
        </MessageScroller>
      </MessageScrollerProvider>
      <form className="flex flex-col gap-3 border-t p-4" onSubmit={onSubmit}>
        <div className="flex gap-2">
          <ModeButton current={mode} mode="autonome" onSelect={setMode} disabled={pending}>
            Autonome
          </ModeButton>
          <ModeButton current={mode} mode="valide" onSelect={setMode} disabled={pending}>
            Validé
          </ModeButton>
        </div>
        <Field>
          <FieldLabel htmlFor="chat-message">Message</FieldLabel>
          <textarea
            id="chat-message"
            value={text}
            disabled={pending}
            placeholder="Décris la carte"
            onChange={(event) => setText(event.target.value)}
            className="min-h-20 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50"
          />
          <FieldDescription>
            {mode === "autonome"
              ? "Aucune question : les hypothèses seront affichées."
              : "Les questions arrivent en un seul round."}
          </FieldDescription>
        </Field>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
        <Button
          type="button"
          disabled={pending || text.trim() === ""}
          onClick={() => void send()}
        >
          {pending ? "En cours" : "Envoyer"}
        </Button>
      </form>
    </div>
  )
}

function SpecStatus({
  projectId,
  specification,
  onSpecification,
}: {
  projectId: string
  specification: SpecificationView
  onSpecification: (specification: SpecificationView) => void
}) {
  if (specification.state === "prete") {
    return (
      <SpecEditor
        key={JSON.stringify(specification.specification)}
        projectId={projectId}
        specification={specification.specification}
        onSaved={onSpecification}
      />
    )
  }
  if (specification.state === "questions") {
    return (
      <p className="border-b px-4 py-3 text-sm text-muted-foreground">
        Réponds à ces questions en un seul message.
      </p>
    )
  }
  if (specification.state === "refusee") {
    return (
      <p className="border-b px-4 py-3 text-sm text-destructive">
        {specification.explanation}
      </p>
    )
  }
  return null
}

function SpecEditor({
  projectId,
  specification,
  onSaved,
}: {
  projectId: string
  specification: BoardSpecification
  onSaved: (specification: SpecificationView) => void
}) {
  const [draft, setDraft] = useState(() => draftFrom(specification))
  const [pending, setPending] = useState(false)
  const [error, setError] = useState<string | null>(null)

  async function save() {
    const next = draftToSpecification(draft)
    if (typeof next === "string") {
      setError(next)
      return
    }
    setPending(true)
    setError(null)
    try {
      onSaved(await saveSpecification(projectId, next))
    } catch (caught) {
      setError(
        caught instanceof Error
          ? caught.message
          : "Impossible d'enregistrer la spécification."
      )
    } finally {
      setPending(false)
    }
  }

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault()
    void save()
  }

  return (
    <form className="flex max-h-64 flex-col gap-3 overflow-auto border-b p-4" onSubmit={onSubmit}>
      <h3 className="text-sm font-medium">Spécification</h3>
      <Field>
        <FieldLabel htmlFor="spec-name">Nom</FieldLabel>
        <Input
          id="spec-name"
          value={draft.name}
          onChange={(event) => setDraft({ ...draft, name: event.target.value })}
        />
      </Field>
      {draft.blocks.map((block, index) => (
        <Field key={`bloc-${index}`}>
          <FieldLabel htmlFor={`bloc-${index}`}>Bloc {index + 1}</FieldLabel>
          <Input
            id={`bloc-${index}`}
            value={block.name}
            onChange={(event) => updateBlock(setDraft, index, { name: event.target.value })}
          />
          <Input
            aria-label={`Rôle du bloc ${index + 1}`}
            value={block.role}
            onChange={(event) => updateBlock(setDraft, index, { role: event.target.value })}
          />
        </Field>
      ))}
      {draft.rails.map((rail, index) => (
        <Field key={`rail-${index}`}>
          <FieldLabel htmlFor={`rail-${index}`}>Rail {index + 1}</FieldLabel>
          <Input
            id={`rail-${index}`}
            value={rail.name}
            onChange={(event) => updateRail(setDraft, index, { name: event.target.value })}
          />
          <Input
            aria-label={`Tension du rail ${index + 1} en volts`}
            inputMode="decimal"
            value={rail.voltage}
            onChange={(event) => updateRail(setDraft, index, { voltage: event.target.value })}
          />
          <Input
            aria-label={`Courant du rail ${index + 1} en ampères`}
            inputMode="decimal"
            value={rail.current}
            onChange={(event) => updateRail(setDraft, index, { current: event.target.value })}
          />
        </Field>
      ))}
      <Field>
        <FieldLabel htmlFor="spec-interfaces">Interfaces</FieldLabel>
        <Input
          id="spec-interfaces"
          value={draft.interfaces}
          onChange={(event) => setDraft({ ...draft, interfaces: event.target.value })}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="spec-width">Dimensions max (mm)</FieldLabel>
        <Input
          id="spec-width"
          inputMode="decimal"
          value={draft.width}
          onChange={(event) => setDraft({ ...draft, width: event.target.value })}
        />
        <Input
          aria-label="Hauteur maximale en millimètres"
          inputMode="decimal"
          value={draft.height}
          onChange={(event) => setDraft({ ...draft, height: event.target.value })}
        />
      </Field>
      <div className="flex gap-2">
        <Button
          type="button"
          variant={draft.mode === "autonome" ? "default" : "outline"}
          onClick={() => setDraft({ ...draft, mode: "autonome" })}
        >
          Autonome
        </Button>
        <Button
          type="button"
          variant={draft.mode === "valide" ? "default" : "outline"}
          onClick={() => setDraft({ ...draft, mode: "valide" })}
        >
          Validé
        </Button>
      </div>
      <div className="flex gap-2">
        {([1, 2, 4] as const).map((layers) => (
          <Button
            key={layers}
            type="button"
            variant={draft.layers === layers ? "default" : "outline"}
            onClick={() => setDraft({ ...draft, layers })}
          >
            {layers} couches
          </Button>
        ))}
      </div>
      <Field>
        <FieldLabel htmlFor="spec-budget">Budget</FieldLabel>
        <Input
          id="spec-budget"
          inputMode="decimal"
          value={draft.amount}
          onChange={(event) => setDraft({ ...draft, amount: event.target.value })}
        />
        <Input
          aria-label="Devise"
          value={draft.currency}
          onChange={(event) => setDraft({ ...draft, currency: event.target.value })}
        />
      </Field>
      <Field>
        <FieldLabel htmlFor="spec-assumptions">Hypothèses</FieldLabel>
        <textarea
          id="spec-assumptions"
          value={draft.assumptions}
          onChange={(event) => setDraft({ ...draft, assumptions: event.target.value })}
          className="min-h-16 w-full rounded-lg border border-input bg-transparent px-2.5 py-1 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
        />
      </Field>
      {error ? <p className="text-sm text-destructive">{error}</p> : null}
      <Button type="button" disabled={pending} onClick={() => void save()}>
        {pending ? "En cours" : "Enregistrer"}
      </Button>
    </form>
  )
}

function ModeButton({
  current,
  mode,
  disabled,
  onSelect,
  children,
}: {
  current: DemandMode
  mode: DemandMode
  disabled: boolean
  onSelect: (mode: DemandMode) => void
  children: string
}) {
  return (
    <Button
      type="button"
      variant={current === mode ? "default" : "outline"}
      disabled={disabled}
      onClick={() => onSelect(mode)}
    >
      {children}
    </Button>
  )
}

type Draft = {
  name: string
  blocks: BoardSpecification["blocks"]
  rails: { name: string; voltage: string; current: string }[]
  interfaces: string
  width: string
  height: string
  layers: 1 | 2 | 4
  amount: string
  currency: string
  mode: DemandMode
  assumptions: string
}

function draftFrom(specification: BoardSpecification): Draft {
  return {
    name: specification.name,
    blocks: specification.blocks,
    rails: specification.rails.map((rail) => ({
      name: rail.name,
      voltage: String(rail.voltage_v),
      current: String(rail.current_a),
    })),
    interfaces: specification.interfaces.join(", "),
    width: String(specification.dimensions.max_width_mm),
    height: String(specification.dimensions.max_height_mm),
    layers: specification.layers,
    amount: String(specification.budget.max_amount),
    currency: specification.budget.currency,
    mode: specification.mode,
    assumptions: specification.assumptions.join("\n"),
  }
}

function draftToSpecification(draft: Draft): BoardSpecification | string {
  const width = positive(draft.width)
  const height = positive(draft.height)
  const amount = positive(draft.amount)
  const rails = draft.rails.map((rail) => {
    const voltage = positive(rail.voltage)
    const current = positive(rail.current)
    if (voltage === null || current === null) {
      return null
    }
    return { name: rail.name.trim(), voltage_v: voltage, current_a: current }
  })
  if (width === null || height === null || amount === null || rails.some((rail) => rail === null)) {
    return "Indique une valeur positive."
  }
  return {
    name: draft.name.trim(),
    blocks: draft.blocks.map((block) => ({
      name: block.name.trim(),
      role: block.role.trim(),
    })),
    rails: rails.filter((rail): rail is NonNullable<(typeof rails)[number]> => rail !== null),
    interfaces: draft.interfaces
      .split(",")
      .map((item) => item.trim())
      .filter((item) => item !== ""),
    dimensions: { max_width_mm: width, max_height_mm: height },
    layers: draft.layers,
    budget: { max_amount: amount, currency: draft.currency.trim() },
    mode: draft.mode,
    assumptions: draft.assumptions
      .split("\n")
      .map((item) => item.trim())
      .filter((item) => item !== ""),
  }
}

function positive(value: string): number | null {
  const parsed = Number(value.trim().replace(",", "."))
  if (!Number.isFinite(parsed) || parsed <= 0) {
    return null
  }
  return parsed
}

function updateBlock(
  setDraft: Dispatch<SetStateAction<Draft>>,
  index: number,
  patch: Partial<BoardSpecification["blocks"][number]>
) {
  setDraft((current) => ({
    ...current,
    blocks: current.blocks.map((block, item) =>
      item === index ? { ...block, ...patch } : block
    ),
  }))
}

function updateRail(
  setDraft: Dispatch<SetStateAction<Draft>>,
  index: number,
  patch: Partial<Draft["rails"][number]>
) {
  setDraft((current) => ({
    ...current,
    rails: current.rails.map((rail, item) =>
      item === index ? { ...rail, ...patch } : rail
    ),
  }))
}

function initialMode(specification: SpecificationView): DemandMode {
  if (specification.state === "prete") {
    return specification.specification.mode
  }
  if (specification.state === "questions") {
    return "valide"
  }
  return "autonome"
}
