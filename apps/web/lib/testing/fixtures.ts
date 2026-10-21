/** Typed access to recorded API responses (captured from the real parser; see e2e/fixtures). */
import type {
  Glossary,
  GrammarPresetDetail,
  LanguageDetail,
  LanguageList,
  ParseGrammarResponse,
  ParseResponse,
} from "@/lib/api/types";
import grammarDogs from "@/e2e/fixtures/grammar-parse-dogs.json";
import grammarRejected from "@/e2e/fixtures/grammar-parse-rejected.json";
import grammarTelescope from "@/e2e/fixtures/grammar-parse-telescope.json";
import grammarPresetPp from "@/e2e/fixtures/grammar-preset-pp.json";
import languageEn from "@/e2e/fixtures/language-en.json";
import languages from "@/e2e/fixtures/languages.json";
import parseChild from "@/e2e/fixtures/parse-child.json";
import parseQuestion from "@/e2e/fixtures/parse-question.json";
import parseTelescope from "@/e2e/fixtures/parse-telescope.json";
import schemePtb from "@/e2e/fixtures/scheme-ptb-revised.json";
import schemeUd from "@/e2e/fixtures/scheme-ud-2.json";
import schemeFeats from "@/e2e/fixtures/scheme-ud-feats.json";
import schemeUpos from "@/e2e/fixtures/scheme-ud-upos.json";

export const fixtures = {
  grammarTelescope: grammarTelescope as unknown as ParseGrammarResponse,
  grammarRejected: grammarRejected as unknown as ParseGrammarResponse,
  grammarDogs: grammarDogs as unknown as ParseGrammarResponse,
  grammarPresetPp: grammarPresetPp as unknown as GrammarPresetDetail,
  languages: languages as unknown as LanguageList,
  languageEn: languageEn as unknown as LanguageDetail,
  parseChild: parseChild as unknown as ParseResponse,
  parseQuestion: parseQuestion as unknown as ParseResponse,
  parseTelescope: parseTelescope as unknown as ParseResponse,
  glossaries: {
    "ud-2": schemeUd as unknown as Glossary,
    "ud-upos": schemeUpos as unknown as Glossary,
    "ud-feats": schemeFeats as unknown as Glossary,
    "ptb-revised": schemePtb as unknown as Glossary,
  } as Record<string, Glossary>,
};
