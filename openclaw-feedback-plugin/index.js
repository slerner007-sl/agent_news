import { definePluginEntry } from "openclaw/plugin-sdk/plugin-entry";
import {
  handleBlockedMenuCommand,
  handleBotInfoCallback,
  handleBotInfoRequest,
  handleFeedbackCallback,
  handleKnowledgeInboundClaim,
  handleKnowledgeMessage,
  handleMetricsInfoRequest,
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

    api.registerInteractiveHandler({
      channel: "telegram",
      namespace: "botinfo",
      handler: (ctx) => handleBotInfoCallback(ctx, pluginConfig),
    });

    api.on(
      "inbound_claim",
      async (event, ctx) => {
        const blockedMenu = await handleBlockedMenuCommand(event, ctx, pluginConfig);
        if (blockedMenu?.handled) return blockedMenu;

        return handleKnowledgeInboundClaim(event, ctx, pluginConfig);
      },
      { priority: 300, timeoutMs: 30_000 },
    );

    api.on(
      "before_dispatch",
      async (event, ctx) => {
        const commentResult = await handlePendingComment(event, ctx, pluginConfig);
        if (commentResult?.handled) return commentResult;

        const botInfoResult = await handleBotInfoRequest(event, ctx, pluginConfig);
        if (botInfoResult?.handled) return botInfoResult;

        const metricsInfoResult = await handleMetricsInfoRequest(event, ctx, pluginConfig);
        if (metricsInfoResult?.handled) return metricsInfoResult;

        return handleKnowledgeMessage(event, ctx, pluginConfig);
      },
      { priority: 100, timeoutMs: 15_000 },
    );
  },
});
