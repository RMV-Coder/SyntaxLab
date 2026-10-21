"use client";

import { ExternalLink } from "lucide-react";
import type { ReactNode } from "react";

import { Button } from "@/components/ui/button";
import type { Glossary, GlossaryEntry, LanguageDetail, ParseResponse, SentenceAnalysis } from "@/lib/api/types";
import { lookupLabel, posFamily } from "@/lib/syntax/glossary";
import { posColor } from "@/lib/theme";

import { pathToToken, type Selection, spanText, tokenText } from "./selection";

export interface Glossaries {
  pos?: Glossary;
  features?: Glossary;
  dependency?: Glossary;
  constituency?: Glossary;
}

interface InspectorProps {
  result: ParseResponse | null;
  sentence: SentenceAnalysis | null;
  selection: Selection;
  glossaries: Glossaries;
  language: LanguageDetail | null;
  collapsed: ReadonlySet<string>;
  onSelect: (selection: Selection) => void;
  onToggle: (nodeId: string) => void;
}

/** Where a piece of information comes from. Shown next to every section. */
function Source({ kind }: { kind: "parser" | "curated" }) {
  return (
    <span className="rounded-sm bg-muted px-1.5 py-0.5 text-[0.6875rem] font-medium text-graphite">
      {kind === "parser" ? "Parser output" : "Curated definition"}
    </span>
  );
}

function Section({
  title,
  source,
  children,
}: {
  title: string;
  source?: "parser" | "curated";
  children: ReactNode;
}) {
  return (
    <section className="border-t border-rule py-4 first:border-t-0 first:pt-0">
      <div className="mb-2 flex items-center justify-between gap-2">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        {source ? <Source kind={source} /> : null}
      </div>
      {children}
    </section>
  );
}

function Definition({
  label,
  glossary,
  language,
}: {
  label: string;
  glossary: Glossary | undefined;
  language: string | undefined;
}) {
  const { entry, match, matchedLabel } = lookupLabel(glossary, label);
  if (!entry) {
    return (
      <p className="text-sm text-graphite">
        SyntaxLab has no curated definition for <span className="font-medium">{label}</span> yet.
      </p>
    );
  }
  return <EntryText entry={entry} match={match} matchedLabel={matchedLabel} label={label} language={language} />;
}

function EntryText({
  entry,
  match,
  matchedLabel,
  label,
  language,
}: {
  entry: GlossaryEntry;
  match: string;
  matchedLabel: string | null;
  label: string;
  language: string | undefined;
}) {
  const note = language ? entry.language_notes?.[language] : undefined;
  return (
    <div className="space-y-2 text-sm leading-relaxed">
      <p>
        <span className="font-semibold">{entry.name}.</span> {entry.definition}
      </p>
      {match === "base" ? (
        <p className="text-graphite">
          “{label}” is a subtype of <span className="font-medium">{matchedLabel}</span>; only the
          general relation is described here.
        </p>
      ) : null}
      {entry.textbook ? (
        <p className="text-graphite">
          Closest textbook category: <span className="font-data">{entry.textbook}</span>. The
          correspondence is approximate.
        </p>
      ) : null}
      {note ? <p className="rounded-sm bg-muted p-2">{note}</p> : null}
      {entry.url ? (
        <a
          href={entry.url}
          target="_blank"
          rel="noreferrer"
          className="inline-flex items-center gap-1 text-ink-soft underline underline-offset-2 hover:text-ink"
        >
          Annotation guidelines
          <ExternalLink aria-hidden className="size-3.5" />
        </a>
      ) : null}
    </div>
  );
}

function TokenDetails({ sentence, id, glossaries, language, onSelect }: {
  sentence: SentenceAnalysis;
  id: number;
  glossaries: Glossaries;
  language: string | undefined;
  onSelect: (s: Selection) => void;
}) {
  const token = sentence.tokens.find((t) => t.id === id);
  if (!token) return null;
  const arc = sentence.dependency?.arcs.find((a) => a.dependent === id);
  const dependents = sentence.dependency?.arcs.filter((a) => a.head === id) ?? [];
  const path = pathToToken(sentence, id);
  const nodeLabel = new Map(sentence.constituency?.nodes.map((n) => [n.id, n.label]) ?? []);
  const features = Object.entries(token.feats);

  return (
    <>
      <header className="mb-4">
        <p className="font-data text-3xl leading-tight text-ink">{token.form}</p>
        <p className="mt-1 text-sm text-graphite">
          Word {token.id} of {sentence.tokens.length}
          {token.lemma ? (
            <>
              {", lemma "}
              <span className="font-data italic text-ink">{token.lemma}</span>
            </>
          ) : null}
        </p>
      </header>

      {token.upos ? (
        <Section title="Part of speech" source="parser">
          <p
            className="small-caps mb-2 font-data text-lg font-bold"
            style={{ color: posColor(posFamily(glossaries.pos, token.upos)) }}
          >
            {token.upos}
            {token.xpos ? (
              <span className="ml-2 text-sm font-normal text-graphite">tag {token.xpos}</span>
            ) : null}
          </p>
          <Definition label={token.upos} glossary={glossaries.pos} language={language} />
        </Section>
      ) : null}

      {features.length > 0 ? (
        <Section title="Grammatical features" source="parser">
          <dl className="space-y-1.5 text-sm">
            {features.map(([feature, value]) => {
              const entry = glossaries.features?.entries[feature];
              const values = value.split(",").map((v) => entry?.values?.[v]?.name ?? v);
              return (
                <div key={feature} className="flex justify-between gap-3">
                  <dt className="text-graphite" title={entry?.definition}>
                    {entry?.name ?? feature}
                  </dt>
                  <dd className="text-right text-ink">
                    {values.join(", ")}
                    <span className="ml-1.5 text-xs text-graphite">
                      {feature}={value}
                    </span>
                  </dd>
                </div>
              );
            })}
          </dl>
        </Section>
      ) : null}

      {arc ? (
        <Section title="Dependency" source="parser">
          <p className="mb-2 text-sm">
            {arc.head === 0 ? (
              <>This word is the <span className="font-semibold">root</span> of the sentence.</>
            ) : (
              <>
                Depends on{" "}
                <button
                  type="button"
                  className="font-data text-base underline underline-offset-2"
                  onClick={() => onSelect({ kind: "token", id: arc.head })}
                >
                  {tokenText(sentence, arc.head)}
                </button>{" "}
                as{" "}
                <button
                  type="button"
                  className="font-semibold underline underline-offset-2"
                  onClick={() => onSelect({ kind: "arc", dependent: arc.dependent })}
                >
                  {arc.relation}
                </button>
                .
              </>
            )}
          </p>
          {dependents.length > 0 ? (
            <p className="text-sm text-graphite">
              Its dependents:{" "}
              {dependents.map((d, i) => (
                <span key={d.dependent}>
                  {i > 0 ? ", " : ""}
                  <button
                    type="button"
                    className="font-data text-ink underline underline-offset-2"
                    onClick={() => onSelect({ kind: "token", id: d.dependent })}
                  >
                    {tokenText(sentence, d.dependent)}
                  </button>{" "}
                  ({d.relation})
                </span>
              ))}
            </p>
          ) : null}
        </Section>
      ) : null}

      {path.length > 0 ? (
        <Section title="Place in the phrase structure" source="parser">
          <ol className="flex flex-wrap items-center gap-x-1 text-sm" aria-label="Path from the root">
            {path.map((nodeId, i) => (
              <li key={nodeId} className="flex items-center gap-1">
                {i > 0 ? <span aria-hidden className="text-graphite">›</span> : null}
                <button
                  type="button"
                  className="small-caps font-data font-bold text-ink underline-offset-2 hover:underline"
                  onClick={() => onSelect({ kind: "node", id: nodeId })}
                >
                  {nodeLabel.get(nodeId)}
                </button>
              </li>
            ))}
          </ol>
        </Section>
      ) : null}
    </>
  );
}

function NodeDetails({ sentence, id, glossaries, language, collapsed, onToggle, onSelect }: {
  sentence: SentenceAnalysis;
  id: string;
  glossaries: Glossaries;
  language: string | undefined;
  collapsed: ReadonlySet<string>;
  onToggle: (id: string) => void;
  onSelect: (s: Selection) => void;
}) {
  const tree = sentence.constituency;
  const node = tree?.nodes.find((n) => n.id === id);
  if (!tree || !node) return null;
  const byId = new Map(tree.nodes.map((n) => [n.id, n]));
  const isPhrase = node.token_id == null;
  return (
    <>
      <header className="mb-4">
        <p className="small-caps font-data text-3xl font-bold leading-tight text-ink">{node.label}</p>
        <p className="mt-1 font-data text-lg text-ink-soft">“{spanText(sentence, node.span[0], node.span[1])}”</p>
      </header>
      <Section title="What this label means" source="curated">
        <Definition label={node.label} glossary={glossaries.constituency} language={language} />
      </Section>
      {isPhrase ? (
        <Section title="Constituents" source="parser">
          <ul className="space-y-1 text-sm">
            {node.children.map((childId) => {
              const child = byId.get(childId)!;
              return (
                <li key={childId} className="flex items-baseline gap-2">
                  <button
                    type="button"
                    className="small-caps min-w-12 text-left font-data font-bold text-ink hover:underline"
                    onClick={() => onSelect({ kind: "node", id: childId })}
                  >
                    {child.label}
                  </button>
                  <span className="font-data text-ink-soft">{spanText(sentence, child.span[0], child.span[1])}</span>
                </li>
              );
            })}
          </ul>
          {id !== tree.root ? (
            <Button variant="outline" size="sm" className="mt-3" onClick={() => onToggle(id)}>
              {collapsed.has(id) ? "Show internal structure" : "Collapse into a triangle"}
            </Button>
          ) : null}
        </Section>
      ) : node.token_id != null ? (
        <Section title="Word" source="parser">
          <button
            type="button"
            className="font-data text-lg underline underline-offset-2"
            onClick={() => onSelect({ kind: "token", id: node.token_id! })}
          >
            {tokenText(sentence, node.token_id)}
          </button>
        </Section>
      ) : null}
    </>
  );
}

function ArcDetails({ sentence, dependent, glossaries, language, onSelect }: {
  sentence: SentenceAnalysis;
  dependent: number;
  glossaries: Glossaries;
  language: string | undefined;
  onSelect: (s: Selection) => void;
}) {
  const arc = sentence.dependency?.arcs.find((a) => a.dependent === dependent);
  if (!arc) return null;
  return (
    <>
      <header className="mb-4">
        <p className="text-2xl font-semibold leading-tight text-ink">{arc.relation}</p>
        <p className="mt-1 text-sm text-graphite">
          <button type="button" className="font-data text-base text-ink underline underline-offset-2" onClick={() => onSelect({ kind: "token", id: arc.dependent })}>
            {tokenText(sentence, arc.dependent)}
          </button>{" "}
          {arc.head === 0 ? (
            "is the root of the sentence"
          ) : (
            <>
              depends on{" "}
              <button type="button" className="font-data text-base text-ink underline underline-offset-2" onClick={() => onSelect({ kind: "token", id: arc.head })}>
                {tokenText(sentence, arc.head)}
              </button>
            </>
          )}
        </p>
      </header>
      <Section title="What this relation means" source="curated">
        <Definition label={arc.relation} glossary={glossaries.dependency} language={language} />
      </Section>
    </>
  );
}

function Provenance({ result, language }: { result: ParseResponse; language: LanguageDetail | null }) {
  const p = result.provenance;
  const schemeName = new Map(
    (language?.capabilities ?? []).flatMap((c) => (c.scheme ? [[c.scheme.id, c.scheme.name]] : [])),
  );
  return (
    <Section title="How this analysis was produced">
      <p className="mb-2 text-sm">
        Engine <span className="font-medium">{p.engine}</span>
        {p.engine_version ? ` ${p.engine_version}` : ""}, model {p.model ?? "unknown"}.{" "}
        {p.cached ? "Returned from cache." : `Took ${(p.processing_ms / 1000).toFixed(1)} s.`}
      </p>
      <dl className="space-y-1.5 text-xs">
        {p.components.map((c) => (
          <div key={c.capability} className="grid grid-cols-[6.5rem_minmax(0,1fr)] gap-2">
            <dt className="capitalize text-graphite">{c.capability}</dt>
            <dd className="break-all text-ink-soft">
              {c.scheme ? <span className="text-ink">{schemeName.get(c.scheme) ?? c.scheme}</span> : null}
              {c.scheme ? <br /> : null}
              {c.component}
            </dd>
          </div>
        ))}
      </dl>
      <p className="mt-2 text-xs text-graphite">No confidence scores are shown: the parser does not provide calibrated ones.</p>
    </Section>
  );
}

export function Inspector({
  result,
  sentence,
  selection,
  glossaries,
  language,
  collapsed,
  onSelect,
  onToggle,
}: InspectorProps) {
  const lang = result?.language.code;
  return (
    <div aria-live="polite" className="space-y-0">
      {!sentence ? (
        <p className="text-sm text-graphite">
          Details about the selected word, phrase or relation appear here.
        </p>
      ) : !selection ? (
        <Section title="Explore the analysis">
          <p className="text-sm text-ink-soft">
            Select any word, phrase label or arrow to see its category, its role in the sentence,
            and what the label means. Use the arrow keys inside a diagram to move between items.
          </p>
        </Section>
      ) : selection.kind === "token" ? (
        <TokenDetails sentence={sentence} id={selection.id} glossaries={glossaries} language={lang} onSelect={onSelect} />
      ) : selection.kind === "node" ? (
        <NodeDetails
          sentence={sentence}
          id={selection.id}
          glossaries={glossaries}
          language={lang}
          collapsed={collapsed}
          onToggle={onToggle}
          onSelect={onSelect}
        />
      ) : (
        <ArcDetails sentence={sentence} dependent={selection.dependent} glossaries={glossaries} language={lang} onSelect={onSelect} />
      )}

      {result ? <Provenance result={result} language={language} /> : null}

      {language?.notes.length ? (
        <Section title={`Known limitations for ${language.name}`}>
          <ul className="list-disc space-y-1.5 pl-4 text-xs leading-relaxed text-ink-soft">
            {language.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
        </Section>
      ) : null}
    </div>
  );
}
