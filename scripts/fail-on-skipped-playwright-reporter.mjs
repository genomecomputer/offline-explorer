export default class FailOnSkippedReporter {
  skipped = [];

  onTestEnd(test, result) {
    if (result.status === "skipped") this.skipped.push(test.titlePath().join(" > "));
  }

  onEnd() {
    if (!this.skipped.length) return;
    for (const title of this.skipped) {
      console.error(`[electron-e2e] Unexpected skipped test: ${title}`);
    }
    return { status: "failed" };
  }
}
