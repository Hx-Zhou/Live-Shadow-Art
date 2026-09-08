import { mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { dirname, join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const schemaFiles = [
  "continuous-signal.schema.json",
  "gesture-event.schema.json",
  "rig.schema.json",
  "manifest.schema.json",
  "script-act.schema.json",
  "controls.schema.json"
];

const schemas = schemaFiles.map((file) => JSON.parse(readFileSync(join(ROOT, "packages/schemas", file), "utf8")));

const tsOut = join(ROOT, "web/src/shared/schemaIds.ts");
const pyOut = join(ROOT, "server/app/schemas/schema_ids.py");

mkdirSync(dirname(tsOut), { recursive: true });
writeFileSync(
  tsOut,
  [
    "export const schemaIds = [",
    ...schemas.map((schema) => `  ${JSON.stringify(schema.$id)},`),
    "] as const;",
    "",
    "export type SchemaId = (typeof schemaIds)[number];",
    ""
  ].join("\n"),
  "utf8"
);

mkdirSync(dirname(pyOut), { recursive: true });
writeFileSync(
  pyOut,
  [
    "SCHEMA_IDS = (",
    ...schemas.map((schema) => `  ${JSON.stringify(schema.$id)},`),
    ")",
    ""
  ].join("\n"),
  "utf8"
);

console.log(`Generated ${tsOut} and ${pyOut}.`);
