import { copyFile, cp, mkdir, rm, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const rootDir = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const sourceDir = join(rootDir, "app", "static");
const outputDir = join(rootDir, "dist");
const staticOutputDir = join(outputDir, "static");

await rm(outputDir, { recursive: true, force: true });
await mkdir(staticOutputDir, { recursive: true });
await cp(sourceDir, staticOutputDir, { recursive: true });
await copyFile(join(sourceDir, "index.html"), join(outputDir, "index.html"));

const apiBaseUrl = (process.env.AAIS_API_BASE_URL || "").replace(/\/+$/, "");
const config = `window.AAIS_CONFIG = ${JSON.stringify({ apiBaseUrl }, null, 2)};\n`;
await writeFile(join(staticOutputDir, "config.js"), config);

console.log(`Built AAIS static frontend in ${outputDir}`);
console.log(apiBaseUrl ? `Using API base URL: ${apiBaseUrl}` : "Using same-origin API requests.");
