// Copies third-party browser files into static/vendor (build-time only).
import { cpSync, mkdirSync } from "node:fs";

const files = [
  ["node_modules/htmx.org/dist/htmx.min.js", "static/vendor/htmx.min.js"],
  ["node_modules/@alpinejs/csp/dist/cdn.min.js", "static/vendor/alpine-csp.min.js"],
  ["node_modules/@fontsource-variable/inter/files/inter-latin-wght-normal.woff2",
   "static/vendor/fonts/inter-latin-wght-normal.woff2"],
  ["node_modules/@fontsource-variable/inter/files/inter-latin-ext-wght-normal.woff2",
   "static/vendor/fonts/inter-latin-ext-wght-normal.woff2"],
];
mkdirSync("static/vendor/fonts", { recursive: true });
for (const [src, dest] of files) cpSync(src, dest);
console.log(`vendored ${files.length} files`);
