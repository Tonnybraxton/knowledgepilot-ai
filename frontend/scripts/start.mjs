import { cp, access } from "node:fs/promises";

const root = new URL("../", import.meta.url);
const standalone = new URL(".next/standalone/", root);

try {
  await access(new URL("server.js", standalone));
} catch {
  throw new Error("Production build missing. Run npm run build before npm start.");
}

// Next.js leaves static assets outside the standalone bundle by default.
await cp(new URL(".next/static/", root), new URL(".next/static/", standalone), {
  recursive: true,
});
try {
  await access(new URL("public/", root));
  await cp(new URL("public/", root), new URL("public/", standalone), { recursive: true });
} catch (error) {
  if (error.code !== "ENOENT") throw error;
}

process.env.HOSTNAME ??= "0.0.0.0";
await import(new URL("server.js", standalone).href);
