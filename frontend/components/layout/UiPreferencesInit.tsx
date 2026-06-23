"use client";

import { useEffect } from "react";

import { applyChatFontSize, subscribeChatFontSize } from "@/lib/uiPreferences";

export function UiPreferencesInit() {
  useEffect(() => {
    applyChatFontSize();
    return subscribeChatFontSize(() => applyChatFontSize());
  }, []);

  return null;
}
