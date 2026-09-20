import { execFileSync } from "node:child_process";
import { mkdtempSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const PINNED_COMMIT = "f2efb313d113149c6ddc9656307a605a7619f8ea";
const upstreamRoot = process.cwd();
const actualCommit = execFileSync("git", ["rev-parse", "HEAD"], {
  cwd: upstreamRoot,
  encoding: "utf8",
}).trim();
if (actualCommit !== PINNED_COMMIT) {
  throw new Error(`expected upstream ${PINNED_COMMIT}, got ${actualCommit}`);
}

const gateModule = await import(
  pathToFileURL(resolve(upstreamRoot, "packages/gate/dist/index.js")).href
);
const {
  createGate,
  fromB64u,
  generateSigningKey,
  verifyReceiptFile,
} = gateModule;

const receipts = [];
const gate = createGate({
  policy: resolve(upstreamRoot, "tests/fixtures/starter-policy.yaml"),
  signingKey: generateSigningKey(),
  receiptSink: (receipt) => receipts.push(receipt),
});
for (let index = 0; index < 3; index += 1) {
  await gate.authorize({
    sessionId: "tail-probe",
    tool: index % 2 === 0 ? "fs.delete" : "http.get",
    args: { index },
  });
}

function writeReceipts(values) {
  const path = join(
    mkdtempSync(join(tmpdir(), "eg-tail-probe-")),
    "receipts.jsonl",
  );
  writeFileSync(path, `${values.map((value) => JSON.stringify(value)).join("\n")}\n`);
  return path;
}

function summary(report) {
  return { breaks: report.breaks, ok: report.ok, total: report.total };
}

const publicKey = fromB64u(gate.publicKey());
const full = verifyReceiptFile(writeReceipts(receipts), publicKey);
const tailDeleted = verifyReceiptFile(writeReceipts(receipts.slice(0, -1)), publicKey);
const result = {
  finding: "present-record verification does not establish terminal completeness",
  full: summary(full),
  tail_deleted: summary(tailDeleted),
  upstream_commit: actualCommit,
};

process.stdout.write(`${JSON.stringify(result, null, 2)}\n`);
