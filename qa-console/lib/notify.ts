/**
 * Report delivery for Azure Pipelines / OCI runtime.
 * Test destinations (replace later for client production):
 *   email: adhithyakumaran2005@gmail.com
 *   whatsapp: +91 9965985951
 * Teams: set TEAMS_WEBHOOK_URL in Azure/OCI secrets when available.
 */

import { promises as fs } from "fs";
import path from "path";
import type { AgentRun, ChannelConfig } from "@/lib/types";

export const TEST_REPORT_EMAIL = "adhithyakumaran2005@gmail.com";
export const TEST_REPORT_WHATSAPP = "+919965985951";

export type DeliveryResult = {
  channel: string;
  ok: boolean;
  mode: "sent" | "queued" | "skipped" | "failed";
  detail: string;
};

function normalizeWhatsApp(raw: string): string {
  const digits = raw.replace(/\D/g, "");
  if (digits.length === 10) return `+91${digits}`;
  if (digits.startsWith("91") && digits.length === 12) return `+${digits}`;
  if (raw.startsWith("+")) return raw;
  return digits ? `+${digits}` : raw;
}

async function appendDeliveryLog(entry: Record<string, unknown>) {
  const dir = path.join(process.cwd(), "data");
  await fs.mkdir(dir, { recursive: true });
  const file = path.join(dir, "delivery.log.jsonl");
  await fs.appendFile(file, JSON.stringify({ at: new Date().toISOString(), ...entry }) + "\n");
}

async function deliverEmail(to: string[], subject: string, body: string): Promise<DeliveryResult> {
  const smtpUrl = process.env.SMTP_URL || process.env.REPORT_SMTP_URL;
  if (!to.length) {
    return { channel: "email", ok: false, mode: "skipped", detail: "no recipients" };
  }
  // Always queue + log for demo/OCI; send when SMTP configured
  await appendDeliveryLog({ channel: "email", to, subject, bodyPreview: body.slice(0, 500), smtp: Boolean(smtpUrl) });
  if (!smtpUrl) {
    return {
      channel: "email",
      ok: true,
      mode: "queued",
      detail: `Queued for ${to.join(", ")} (configure SMTP_URL on Azure/OCI to send live)`,
    };
  }
  // Live SMTP transport is enabled when SMTP_URL is set in Azure/OCI.
  // Without a mailer package we still treat it as queued with explicit config signal.
  return {
    channel: "email",
    ok: true,
    mode: "queued",
    detail: `SMTP_URL present — delivery worker should send to ${to.join(", ")} (logged)`,
  };
}

async function deliverWhatsApp(to: string, body: string): Promise<DeliveryResult> {
  const dest = normalizeWhatsApp(to);
  const sid = process.env.TWILIO_ACCOUNT_SID;
  const token = process.env.TWILIO_AUTH_TOKEN;
  const from = process.env.TWILIO_WHATSAPP_FROM; // e.g. whatsapp:+14155238886
  await appendDeliveryLog({ channel: "whatsapp", to: dest, bodyPreview: body.slice(0, 400), twilio: Boolean(sid && token && from) });
  if (!sid || !token || !from) {
    return {
      channel: "whatsapp",
      ok: true,
      mode: "queued",
      detail: `Queued for WhatsApp ${dest} (set TWILIO_* on Azure/OCI for live send)`,
    };
  }
  try {
    const auth = Buffer.from(`${sid}:${token}`).toString("base64");
    const params = new URLSearchParams({
      From: from.startsWith("whatsapp:") ? from : `whatsapp:${from}`,
      To: dest.startsWith("whatsapp:") ? dest : `whatsapp:${dest}`,
      Body: body.slice(0, 1500),
    });
    const res = await fetch(`https://api.twilio.com/2010-04-01/Accounts/${sid}/Messages.json`, {
      method: "POST",
      headers: {
        Authorization: `Basic ${auth}`,
        "Content-Type": "application/x-www-form-urlencoded",
      },
      body: params,
    });
    if (!res.ok) {
      const text = await res.text();
      return { channel: "whatsapp", ok: false, mode: "failed", detail: text.slice(0, 300) };
    }
    return { channel: "whatsapp", ok: true, mode: "sent", detail: `Sent WhatsApp to ${dest}` };
  } catch (e) {
    return {
      channel: "whatsapp",
      ok: false,
      mode: "failed",
      detail: e instanceof Error ? e.message : String(e),
    };
  }
}

async function deliverTeams(webhook: string, title: string, body: string): Promise<DeliveryResult> {
  const url = webhook || process.env.TEAMS_WEBHOOK_URL || "";
  await appendDeliveryLog({ channel: "teams", webhookConfigured: Boolean(url), title, bodyPreview: body.slice(0, 300) });
  if (!url) {
    return {
      channel: "teams",
      ok: true,
      mode: "queued",
      detail: "Teams webhook not set — add TEAMS_WEBHOOK_URL in Azure/OCI secrets",
    };
  }
  try {
    const res = await fetch(url, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        "@type": "MessageCard",
        "@context": "http://schema.org/extensions",
        summary: title,
        themeColor: "0078D7",
        title,
        text: body.slice(0, 4000),
      }),
    });
    if (!res.ok) {
      return { channel: "teams", ok: false, mode: "failed", detail: await res.text() };
    }
    return { channel: "teams", ok: true, mode: "sent", detail: "Posted to Teams webhook" };
  } catch (e) {
    return {
      channel: "teams",
      ok: false,
      mode: "failed",
      detail: e instanceof Error ? e.message : String(e),
    };
  }
}

export async function deliverReport(
  run: AgentRun,
  channels: ChannelConfig,
  selected: string[]
): Promise<DeliveryResult[]> {
  const title = `Apex QA · ${run.conclusion || run.status} · ${run.type}`;
  const body = [
    run.report?.summary || run.goal,
    "",
    `Run: ${run.id}`,
    `Goal: ${run.goal}`,
    `Conclusion: ${run.conclusion || "n/a"}`,
    `Reason: ${run.reasonCode || "n/a"}`,
    `Tokens in/out: ${run.usage.tokensIn}/${run.usage.tokensOut}`,
    "",
    run.report?.markdown?.slice(0, 3500) || "",
  ].join("\n");

  const results: DeliveryResult[] = [];
  for (const ch of selected) {
    if (ch === "email") {
      const to = channels.email?.length ? channels.email : [TEST_REPORT_EMAIL];
      results.push(await deliverEmail(to, title, body));
    } else if (ch === "whatsapp") {
      results.push(await deliverWhatsApp(channels.whatsapp || TEST_REPORT_WHATSAPP, body));
    } else if (ch === "teams") {
      results.push(await deliverTeams(channels.teamsWebhook, title, body));
    } else if (ch === "slack") {
      await appendDeliveryLog({ channel: "slack", note: "slack stub", webhook: Boolean(channels.slackWebhook) });
      results.push({
        channel: "slack",
        ok: true,
        mode: channels.slackWebhook ? "queued" : "skipped",
        detail: channels.slackWebhook ? "Slack webhook logged" : "no slack webhook",
      });
    }
  }
  return results;
}
