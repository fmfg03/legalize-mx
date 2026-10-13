const fs = require("node:fs");
const assert = require("node:assert/strict");
const { chromium } = require("playwright");

(async () => {
  const input = JSON.parse(fs.readFileSync(process.env.LEGALIZE_BROWSER_FIXTURE, "utf8"));
  const browser = await chromium.launch({ executablePath: "/usr/bin/chromium", headless: true, args: ["--no-sandbox"] });
  try {
    const page = await browser.newPage();
    const errors = [];
    page.on("pageerror", (error) => errors.push(error.message));
    await page.goto(input.console);
    await page.waitForFunction(() => document.querySelector("#releaseVersionSelect").options.length > 1);
    assert(await page.locator("#evaluateReleaseButton").isDisabled());
    await page.evaluate((accessToken) => window.dispatchEvent(new CustomEvent("legalize-auth-session", { detail: { accessToken, actor_id: "ignored", role: "admin" } })), input.firstToken);
    await page.selectOption("#releaseVersionSelect", input.versionId);
    await page.fill('#releaseForm textarea[name="bundle"]', JSON.stringify(input.bundle));
    await page.click("#evaluateReleaseButton");
    await page.waitForFunction(() => !document.querySelector("#confirmReleaseButton").disabled);
    assert(JSON.parse(await page.locator("#releaseGateResult").textContent()).verdict === "approved");
    await page.fill('#releaseForm textarea[name="bundle"]', JSON.stringify({ ...input.bundle, request_id: "changed" }));
    assert(await page.locator("#confirmReleaseButton").isDisabled());
    await page.fill('#releaseForm textarea[name="bundle"]', JSON.stringify(input.bundle));
    await page.click("#evaluateReleaseButton");
    await page.waitForFunction(() => !document.querySelector("#confirmReleaseButton").disabled);
    await page.evaluate((accessToken) => window.dispatchEvent(new CustomEvent("legalize-auth-session", { detail: { accessToken } })), input.secondToken);
    assert(await page.locator("#confirmReleaseButton").isDisabled());
    await page.click("#evaluateReleaseButton");
    await page.waitForFunction(() => !document.querySelector("#confirmReleaseButton").disabled);
    await page.click("#confirmReleaseButton");
    await page.waitForFunction(() => document.querySelector("#statusStrip").textContent.includes("Liberación registrada"));
    const receipt = JSON.parse(await page.locator("#releaseGateResult").textContent());
    assert.equal(receipt.verdict, "approved");
    assert.equal(receipt.created_by_user_id, input.secondActorId);
    assert(receipt.execution_id);
    await page.click("#evaluateReleaseButton");
    await page.waitForFunction(() => !document.querySelector("#confirmReleaseButton").disabled);
    let releaseResponse;
    let unblockResponse;
    let requestReached;
    const reached = new Promise((resolve) => { requestReached = resolve; });
    const blocked = new Promise((resolve) => { unblockResponse = resolve; });
    await page.route("**/app-api/expedientes/*/release", async (route) => {
      if (route.request().postDataJSON().action !== "release") return route.continue();
      releaseResponse = await route.fetch();
      requestReached();
      await blocked;
      await route.fulfill({ response: releaseResponse });
    });
    await page.click("#confirmReleaseButton");
    await reached;
    await page.evaluate((accessToken) => window.dispatchEvent(new CustomEvent("legalize-auth-session", { detail: { accessToken } })), input.firstToken);
    await page.selectOption("#releaseVersionSelect", "");
    unblockResponse();
    await page.waitForFunction(() => document.querySelector("#statusStrip").textContent.includes("La operación anterior terminó"));
    assert.equal(await page.locator("#releaseGateResult").textContent(), "");
    const priorReceipt = await releaseResponse.json();
    assert.equal(priorReceipt.created_by_user_id, input.secondActorId);
    assert(await page.locator("#confirmReleaseButton").isDisabled());
    await page.unroute("**/app-api/expedientes/*/release");
    await page.evaluate(() => window.dispatchEvent(new CustomEvent("legalize-auth-session", { detail: {} })));
    assert(await page.locator("#evaluateReleaseButton").isDisabled());
    assert(await page.locator("#confirmReleaseButton").isDisabled());
    assert.deepEqual(errors, []);
    console.log(JSON.stringify({ browser: "chromium", approved_actor: receipt.created_by_user_id, execution_id: receipt.execution_id, session_and_bundle_invalidation: true, confirmation_race_checked: true, page_errors: errors.length }));
  } finally {
    await browser.close();
  }
})().catch((error) => { console.error(error.message); process.exit(1); });
