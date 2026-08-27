import { useAppStore } from "@/store/appStore";
import { getDictionary } from "@/i18n";

export function useTranslation() {
  const language = useAppStore((s) => s.language);
  const setLanguage = useAppStore((s) => s.setLanguage);
  const t = getDictionary(language);
  return { t, language, setLanguage };
}
