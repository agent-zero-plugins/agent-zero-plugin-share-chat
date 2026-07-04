import { Given, When, Then } from "../../_testkit/e2e/bdd/bdd-fixtures";
import { expect } from "@playwright/test";

// share-chat is a pure UI plugin (no LLM, no seam). We just need a REAL active chat
// (chat_create — the fork keeps it selected) so getContext() is truthy and the
// chat-top-end button renders.
let ctx = "";
const openChat = async (page: any) => {
  await page.goto("/", { waitUntil: "domcontentloaded" });
  await page.waitForTimeout(1500);
  ctx = await page.evaluate(async () => {
    const { callJsonApi } = await import("/js/api.js");
    const r = await callJsonApi("/chat_create", {});
    const id = (r && (r.ctxid || r.context)) || "";
    if (id) (globalThis as any).setContext(id);
    return id;
  });
  if (!ctx) throw new Error("chat_create returned no ctxid");
};

Given("I am in a chat", async ({ loggedInPage }: any) => {
  await openChat(loggedInPage);
});

Then("a share control is available in the chat toolbar", async ({ loggedInPage }: any) => {
  await expect(loggedInPage.locator(".share-chat-btn")).toBeVisible({ timeout: 12000 });
});

When("I share the chat", async ({ loggedInPage }: any) => {
  // Capture whatever the plugin copies (both the clipboard-API path and the
  // execCommand fallback) so we can assert the link without OS clipboard read.
  await loggedInPage.evaluate(() => {
    (window as any).__copied = null;
    if (navigator.clipboard) {
      navigator.clipboard.writeText = (t: string) => { (window as any).__copied = t; return Promise.resolve(); };
    }
    document.execCommand = ((cmd: string) => {
      if (cmd === "copy") { const ta = document.querySelector("textarea"); if (ta) (window as any).__copied = (ta as HTMLTextAreaElement).value; }
      return true;
    }) as any;
  });
  await expect(loggedInPage.locator(".share-chat-btn")).toBeVisible({ timeout: 12000 });
  await loggedInPage.locator(".share-chat-btn").click();
});

Then("a link to this chat is copied to my clipboard", async ({ loggedInPage }: any) => {
  const copied = await loggedInPage.evaluate(() => (window as any).__copied);
  expect(copied, "the share button should have copied something").toBeTruthy();
});

Then("the link identifies this conversation", async ({ loggedInPage }: any) => {
  const copied = await loggedInPage.evaluate(() => (window as any).__copied);
  expect(String(copied)).toContain("ctxid=" + ctx);
});

Then("the control confirms the link was copied", async ({ loggedInPage }: any) => {
  // On a successful copy the button gains the green "copied" accent (.share-copied).
  await expect(loggedInPage.locator(".share-chat-btn.share-copied")).toBeVisible({ timeout: 5000 });
});
