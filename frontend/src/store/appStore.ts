import { create } from "zustand";
import type { CitizenIdentity, Language, StaffProfile } from "@/types";

const LANG_KEY = "civicfix_lang";
const CITIZEN_KEY = "civicfix_citizen";
const STAFF_TOKEN_KEY = "civicfix_staff_token";
const STAFF_PROFILE_KEY = "civicfix_staff_profile";
const CITIZEN_TOKEN_KEY = "civicfix_citizen_token";
const CITIZEN_AUTH_IDENTITY_KEY = "civicfix_citizen_auth_identity";

interface AppState {
  language: Language;
  setLanguage: (lang: Language) => void;

  // Guest identity (name + mobile) — used to prefill/skip the report
  // wizard's identity step. Set by both guest reporting AND logged-in
  // citizens (see setCitizenAuth), so the report flow never needs to
  // know or care whether the citizen is logged in.
  citizen: CitizenIdentity | null;
  setCitizen: (c: CitizenIdentity) => void;

  // Logged-in citizen session (separate from the lightweight guest
  // identity above). null when browsing as a guest.
  citizenToken: string | null;
  citizenAuthIdentity: CitizenIdentity | null;
  setCitizenAuth: (token: string, identity: CitizenIdentity) => void;
  clearCitizenAuth: () => void;

  staffToken: string | null;
  staffProfile: StaffProfile | null;
  setStaffAuth: (token: string, profile: StaffProfile) => void;
  clearStaffAuth: () => void;

  isOnline: boolean;
  setOnline: (online: boolean) => void;

  syncState: "idle" | "syncing";
  setSyncState: (s: "idle" | "syncing") => void;
}

function loadJSON<T>(key: string): T | null {
  try {
    const raw = localStorage.getItem(key);
    return raw ? (JSON.parse(raw) as T) : null;
  } catch {
    return null;
  }
}

export const useAppStore = create<AppState>((set) => ({
  language: (localStorage.getItem(LANG_KEY) as Language) || "en",
  setLanguage: (lang) => {
    localStorage.setItem(LANG_KEY, lang);
    set({ language: lang });
  },

  citizen: loadJSON<CitizenIdentity>(CITIZEN_KEY),
  setCitizen: (c) => {
    localStorage.setItem(CITIZEN_KEY, JSON.stringify(c));
    set({ citizen: c });
  },

  citizenToken: localStorage.getItem(CITIZEN_TOKEN_KEY),
  citizenAuthIdentity: loadJSON<CitizenIdentity>(CITIZEN_AUTH_IDENTITY_KEY),
  setCitizenAuth: (token, identity) => {
    localStorage.setItem(CITIZEN_TOKEN_KEY, token);
    localStorage.setItem(CITIZEN_AUTH_IDENTITY_KEY, JSON.stringify(identity));
    // Also set the guest identity so the report wizard immediately skips
    // straight past the identity step, exactly as an existing guest would.
    localStorage.setItem(CITIZEN_KEY, JSON.stringify(identity));
    set({ citizenToken: token, citizenAuthIdentity: identity, citizen: identity });
  },
  clearCitizenAuth: () => {
    localStorage.removeItem(CITIZEN_TOKEN_KEY);
    localStorage.removeItem(CITIZEN_AUTH_IDENTITY_KEY);
    localStorage.removeItem(CITIZEN_KEY);
    set({ citizenToken: null, citizenAuthIdentity: null, citizen: null });
  },

  staffToken: localStorage.getItem(STAFF_TOKEN_KEY),
  staffProfile: loadJSON<StaffProfile>(STAFF_PROFILE_KEY),
  setStaffAuth: (token, profile) => {
    localStorage.setItem(STAFF_TOKEN_KEY, token);
    localStorage.setItem(STAFF_PROFILE_KEY, JSON.stringify(profile));
    set({ staffToken: token, staffProfile: profile });
  },
  clearStaffAuth: () => {
    localStorage.removeItem(STAFF_TOKEN_KEY);
    localStorage.removeItem(STAFF_PROFILE_KEY);
    set({ staffToken: null, staffProfile: null });
  },

  isOnline: navigator.onLine,
  setOnline: (online) => set({ isOnline: online }),

  syncState: "idle",
  setSyncState: (s) => set({ syncState: s }),
}));
