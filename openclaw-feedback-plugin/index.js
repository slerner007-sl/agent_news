import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import {
  handleFeedbackCallback,
  handlePendingComment,
} from "./plugin-core.js";

export default definePluginEntry({
  id: "gosb-feedback",
  name: "GOSB News Feedback",
  description: "Handles Telegram digest feedback inside OpenClaw polling.",
  register(api) {
    const pluginConfig = api.pluginConfig ?? {};

    for (const namespace of ["useful", "boring", "comment"]) {
      api.registerInteractiveHandler({
        channel: "telegram",
        namespace,
        handler: (ctx) => handleFeedbackCallback(ctx, pluginConfig),
      });
    }

    api.on(
      "before_dispatch",
      (event, ctx) => handlePendingComment(event, ctx, pluginConfig),
      { priority: 100, timeoutMs: 15_000 },
    );
  },
});
