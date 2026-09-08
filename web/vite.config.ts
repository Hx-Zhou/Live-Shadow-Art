import { existsSync, readdirSync, readFileSync, statSync } from "node:fs";
import { relative, resolve, sep } from "node:path";
import { fileURLToPath } from "node:url";
import { defineConfig, type Plugin } from "vite";

const assetRoot = fileURLToPath(new URL("../assets", import.meta.url));
const publicAssetDirectories = ["backgrounds", "characters", "rigs"];

function contentType(filePath: string) {
  if (filePath.endsWith(".png")) return "image/png";
  if (filePath.endsWith(".json")) return "application/json; charset=utf-8";
  return "application/octet-stream";
}

function listFiles(directory: string): string[] {
  return readdirSync(directory, { withFileTypes: true }).flatMap((entry) => {
    const entryPath = resolve(directory, entry.name);
    return entry.isDirectory() ? listFiles(entryPath) : [entryPath];
  });
}

function resolveAsset(urlPath: string) {
  const match = /^\/(backgrounds|characters|rigs)\/(.+)$/.exec(urlPath);
  if (!match) return null;
  const directory = resolve(assetRoot, match[1]);
  const filePath = resolve(directory, decodeURIComponent(match[2]));
  return filePath.startsWith(`${directory}${sep}`) && existsSync(filePath) && statSync(filePath).isFile() ? filePath : null;
}

function assetLibrary(): Plugin {
  return {
    name: "shadow-stage-asset-library",
    configureServer(server) {
      server.middlewares.use((request, response, next) => {
        const filePath = request.url ? resolveAsset(request.url.split("?")[0]) : null;
        if (!filePath) return next();
        response.statusCode = 200;
        response.setHeader("Content-Type", contentType(filePath));
        response.end(readFileSync(filePath));
      });
    },
    generateBundle() {
      for (const directory of publicAssetDirectories) {
        for (const filePath of listFiles(resolve(assetRoot, directory))) {
          this.emitFile({
            type: "asset",
            fileName: relative(assetRoot, filePath),
            source: readFileSync(filePath)
          });
        }
      }
    }
  };
}

export default defineConfig({
  publicDir: false,
  plugins: [assetLibrary()],
  server: {
    port: 5173,
    strictPort: false
  }
});
