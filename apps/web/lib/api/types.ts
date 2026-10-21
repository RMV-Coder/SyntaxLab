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

// Algorithm Lab
export type GrammarPresetList = Schemas["GrammarPresetList"];
export type GrammarPresetSummary = Schemas["GrammarPresetSummary"];
export type GrammarPresetDetail = Schemas["GrammarPresetDetail"];
export type GrammarExample = Schemas["GrammarExample"];
export type GrammarSummary = Schemas["GrammarSummary"];
export type GrammarRule = Schemas["GrammarRule"];
export type GrammarDiagnostic = Schemas["GrammarDiagnostic"];
export type ValidateGrammarResponse = Schemas["ValidateGrammarResponse"];
export type ParseGrammarRequest = Schemas["ParseGrammarRequest"];
export type ParseGrammarResponse = Schemas["ParseGrammarResponse"];
export type ChartItem = Schemas["ChartItemOut"];
export type ItemRef = Schemas["ItemRefOut"];
export type TraceEvent = Schemas["TraceEventOut"];
export type DerivationTree = Schemas["DerivationTree"];

// Learn
export type ExerciseKind = Schemas["ExerciseSummary"]["kind"];
export type ExerciseSummary = Schemas["ExerciseSummary"];
export type ExerciseList = Schemas["ExerciseList"];
export type ExerciseDetail = Schemas["ExerciseDetail"];
export type LabelOption = Schemas["LabelOption"];
export type CheckRequest = Schemas["CheckRequest"];
export type CheckResponse = Schemas["CheckResponse"];
export type PosFeedback = Schemas["PosFeedback"];
export type DependencyFeedback = Schemas["DependencyFeedback"];
export type ConstituencyFeedback = Schemas["ConstituencyFeedback"];
export type ConstituentFeedback = Schemas["ConstituentFeedback"];
export type StructureProblem = Schemas["StructureProblem"];
