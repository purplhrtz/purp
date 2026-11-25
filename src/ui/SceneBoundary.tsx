"use client";
import { Component, type ReactNode } from "react";
import { useStore } from "@/state/store";

/** If the 3D room can't load (old GPU, blocked asset, context loss), stay on the still + hotspots. */
export class SceneBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };
  static getDerivedStateFromError() {
    return { failed: true };
  }
  componentDidCatch(err: unknown) {
    console.warn("[purplhrtz] 3D room unavailable, using the still", err);
    useStore.getState().set({ webgl: "no", sceneReady: false });
  }
  render() {
    return this.state.failed ? null : this.props.children;
  }
}
