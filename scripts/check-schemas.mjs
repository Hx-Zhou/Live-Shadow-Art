import { existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("..", import.meta.url).pathname;
const errors = [];

function readJson(relativePath) {
  try {
    return JSON.parse(readFileSync(join(ROOT, relativePath), "utf8"));
  } catch (error) {
    errors.push(`${relativePath}: ${error.message}`);
    return null;
  }
}

function requireFile(relativePath) {
  if (!existsSync(join(ROOT, relativePath))) {
    errors.push(`Missing file: ${relativePath}`);
  }
}

for (const schema of [
  "gesture-event.schema.json",
  "continuous-signal.schema.json",
  "rig.schema.json",
  "manifest.schema.json",
  "script-act.schema.json",
  "controls.schema.json"
]) {
  readJson(`packages/schemas/${schema}`);
}

const controls = readJson("controls/controls.json");
if (controls) {
  for (const action of ["pinch", "swipe_left", "swipe_right", "raise", "fist", "open_palm"]) {
    if (!controls.gestures.some((binding) => binding.action === action)) {
      errors.push(`controls.json missing gesture binding: ${action}`);
    }
  }
}

for (const rigPath of [
  "assets/rigs/humanoid.json",
  "assets/rigs/animal.json"
]) {
  const rig = readJson(rigPath);
  if (!rig) continue;
  const ids = new Set(rig.nodes.map((node) => node.id));
  if (!ids.has(rig.root)) {
    errors.push(`${rigPath}: missing root node ${rig.root}`);
  }
  for (const node of rig.nodes) {
    if (node.parent !== null && !ids.has(node.parent)) {
      errors.push(`${rigPath}: node ${node.id} missing parent ${node.parent}`);
    }
  }
}

for (const character of ["hero_rabbit", "forest_fox"]) {
  const manifestPath = `assets/characters/${character}/manifest.json`;
  const manifest = readJson(manifestPath);
  if (!manifest) continue;
  requireFile(`assets/characters/${character}/${manifest.rig}`);
  for (const part of manifest.parts) {
    requireFile(`assets/characters/${character}/${part}`);
  }
}

for (const background of ["paper_curtain", "mountain_pass", "moon_bridge"]) {
  readJson(`assets/backgrounds/${background}.json`);
  requireFile(`assets/backgrounds/${background}.png`);
}

const openapi = readFileSync(join(ROOT, "packages/schemas/openapi.yaml"), "utf8");
for (const endpoint of [
  "/api/textures/generate",
  "/api/tasks/{task_id}",
  "/api/assets/{asset_id}",
  "/api/script/generate",
  "/ws/generation/{sid}"
]) {
  if (!openapi.includes(endpoint)) {
    errors.push(`openapi.yaml missing endpoint: ${endpoint}`);
  }
}

if (errors.length > 0) {
  console.error(errors.join("\n"));
  process.exit(1);
}

console.log("Schema and asset contract checks passed.");
