/**
 * Friendly aliases for the generated API contract (lib/api/schema.d.ts).
 * Regenerate with `pnpm api:types` from the repository root after backend schema changes.
 */
import type { components } from "./schema";

type Schemas = components["schemas"];

export type LanguageSummary = Schemas["LanguageSummary"];
export type LanguageDetail = Schemas["LanguageDetail"];
export type LanguageList = Schemas["LanguageList"];
export type LanguageStatus = Schemas["LanguageStatus"];
export type CapabilityInfo = Schemas["CapabilityInfo"];
export type StructureKind = Schemas["StructureKind"];
export type ParseRequest = Schemas["ParseRequest"];
export type ParseResponse = Schemas["ParseResponse"];
export type SentenceAnalysis = Schemas["SentenceAnalysis"];
export type Token = Schemas["Token"];
export type MultiwordToken = Schemas["MultiwordToken"];
export type DependencyArc = Schemas["DependencyArc"];
export type DependencyAnalysis = Schemas["DependencyAnalysis"];
export type ConstituencyNode = Schemas["ConstituencyNode"];
export type ConstituencyAnalysis = Schemas["ConstituencyAnalysis"];
export type Provenance = Schemas["Provenance"];
export type Glossary = Schemas["Glossary"];
export type GlossaryEntry = Schemas["GlossaryEntry"];
export type ErrorBody = Schemas["ErrorBody"];
