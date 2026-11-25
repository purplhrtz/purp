"use client";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";

export type Shot = "overview" | "desk" | "couch" | "cork" | "barry";
export type Tab = "studio" | "listen" | "shop" | "cart";
export type Panel = null | "laptop" | "cork";
export type Modes = { checkout: "stripe" | "demo"; notes: "shared" | "demo"; stripeTestMode: boolean };

export type NowPlaying = { id: string; title: string; src: string; cover: string } | null;

type State = {
  modes: Modes;
  shot: Shot;
  panel: Panel;
  returnFocus: string | null; // id of the control to refocus on Back to room
  laptopAwake: boolean;
  tab: Tab;
  productId: string | null;
  cart: string[];
  soundOn: boolean;
  lampOn: boolean;
  nowPlaying: NowPlaying;
  playing: boolean;
  introDone: boolean;
  sceneReady: boolean;
  webgl: "unknown" | "yes" | "no";
  barryPoke: number; // increments to trigger a reaction
  screenRect: { x: number; y: number; w: number; h: number } | null;
  announce: string;
  checkoutReturn: { result: "success" | "cancelled"; sessionId: string | null } | null;
  // actions
  setModes: (m: Modes) => void;
  go: (shot: Shot, panel?: Panel, from?: string | null) => void;
  back: () => void;
  openLaptop: (from?: string | null, tab?: Tab) => void;
  setTab: (t: Tab) => void;
  showProduct: (id: string | null) => void;
  addToCart: (id: string) => void;
  removeFromCart: (id: string) => void;
  clearCart: () => void;
  setSound: (on: boolean) => void;
  toggleLamp: () => void;
  setNowPlaying: (n: NowPlaying, playing: boolean) => void;
  setPlaying: (p: boolean) => void;
  set: (p: Partial<State>) => void;
};

const label: Record<Shot, string> = {
  overview: "Back in the room, at the foot of the stairs.",
  desk: "At the desk. The laptop is awake.",
  couch: "On the couch, looking across at the desk.",
  cork: "At the corkboard.",
  barry: "Crouched next to Barry on his road case.",
};

export const useStore = create<State>()(
  persist(
    (set, get) => ({
      modes: { checkout: "demo", notes: "demo", stripeTestMode: false },
      shot: "overview",
      panel: null,
      returnFocus: null,
      laptopAwake: false,
      tab: "studio",
      productId: null,
      cart: [],
      soundOn: false,
      lampOn: true,
      nowPlaying: null,
      playing: false,
      introDone: false,
      sceneReady: false,
      webgl: "unknown",
      barryPoke: 0,
      screenRect: null,
      announce: "",
      checkoutReturn: null,
      setModes: (modes) => set({ modes }),
      go: (shot, panel = null, from = null) =>
        set((s) => ({
          shot,
          panel,
          introDone: true,
          returnFocus: from ?? s.returnFocus,
          barryPoke: shot === "barry" ? s.barryPoke + 1 : s.barryPoke,
          announce: label[shot],
        })),
      back: () => set({ shot: "overview", panel: null, introDone: true, announce: label.overview }),
      openLaptop: (from = null, tab) =>
        set((s) => ({
          shot: "desk",
          panel: "laptop",
          laptopAwake: true,
          introDone: true,
          tab: tab ?? s.tab,
          returnFocus: from ?? s.returnFocus,
          announce: "The laptop wakes up. purplhrtz storefront open.",
        })),
      setTab: (tab) => set({ tab, productId: tab === "shop" ? get().productId : null }),
      showProduct: (productId) => set({ productId, tab: "shop" }),
      addToCart: (id) =>
        set((s) => (s.cart.includes(id) ? {} : { cart: [...s.cart, id], announce: "Added to cart." })),
      removeFromCart: (id) => set((s) => ({ cart: s.cart.filter((c) => c !== id), announce: "Removed from cart." })),
      clearCart: () => set({ cart: [] }),
      setSound: (soundOn) => set({ soundOn, announce: soundOn ? "Sound on." : "Sound off." }),
      toggleLamp: () => set((s) => ({ lampOn: !s.lampOn, announce: s.lampOn ? "Lamp off. Violet light only." : "Lamp on." })),
      setNowPlaying: (nowPlaying, playing) => set({ nowPlaying, playing }),
      setPlaying: (playing) => set({ playing }),
      set: (p) => set(p),
    }),
    {
      name: "purplhrtz",
      version: 1,
      // window.localStorage only: avoids Node 26's experimental server-side localStorage during SSR
      storage: createJSONStorage(() => window.localStorage),
      // Only durable things: the cart, where you were in the laptop, and the sound preference.
      partialize: (s) => ({ cart: s.cart, tab: s.tab, productId: s.productId, soundOn: s.soundOn, lampOn: s.lampOn }),
    },
  ),
);
