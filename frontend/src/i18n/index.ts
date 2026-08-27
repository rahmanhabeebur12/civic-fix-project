import en from "./en";
import ta from "./ta";
import type { Language } from "@/types";

export const dictionaries: Record<Language, typeof en> = { en, ta };

export function getDictionary(lang: Language) {
  return dictionaries[lang] ?? en;
}
