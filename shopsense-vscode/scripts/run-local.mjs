import { spawn } from "node:child_process";
import { existsSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const backendDir = path.join(root, "artifacts", "shopsense", "backend");
const windows = process.platform === "win32";
const apiPort = process.env.SHOPSENSE_API_PORT || "8001";
const webPort = process.env.SHOPSENSE_WEB_PORT || "21957";
const python = process.env.PYTHON || (
  windows
    ? path.join(root, ".venv", "Scripts", "python.exe")
    : path.join(root, ".venv", "bin", "python")
);

if (!existsSync(python)) {
  console.error("ShopSense Python environment is missing. Run “ShopSense: Setup” first.");
  process.exit(1);
}

const children = [];
let stopping = false;

function stop(exitCode = 0) {
  if (stopping) return;
  stopping = true;
  process.exitCode = exitCode;
  for (const child of children) {
    if (!child.pid) continue;
    if (windows) {
      spawn("taskkill", ["/pid", String(child.pid), "/t", "/f"], {
        stdio: "ignore",
        windowsHide: true,
      });
    } else {
      child.kill("SIGTERM");
    }
  }
}

function start(label, command, args, options) {
  console.log(`\n==> Starting ${label}`);
  const child = spawn(command, args, {
    ...options,
    stdio: "inherit",
    shell: windows,
    windowsHide: true,
  });
  children.push(child);
  child.on("error", (error) => {
    console.error(`${label} could not start: ${error.message}`);
    stop(1);
  });
  child.on("exit", (code) => {
    if (!stopping) {
      console.error(`${label} stopped${code === 0 ? "" : ` with exit code ${code}`}.`);
      stop(code === 0 ? 0 : code ?? 1);
    }
  });
  return child;
}

const backend = start(
  "FastAPI backend",
  python,
  ["-m", "uvicorn", "capstone.api.main:app", "--host", "127.0.0.1", "--port", apiPort],
  {
    cwd: backendDir,
    env: {
      ...process.env,
      PYTHONPATH: "src",
      PORT: apiPort,
      LLM_PROVIDER: "rules",
      LLM_ENABLED: "false",
    },
  },
);

process.on("SIGINT", () => stop(0));
process.on("SIGTERM", () => stop(0));

const healthUrl = `http://127.0.0.1:${apiPort}/shopsense-backend/health`;
let healthy = false;
for (let attempt = 0; attempt < 180 && !stopping; attempt += 1) {
  if (backend.exitCode !== null) break;
  try {
    const response = await fetch(healthUrl);
    if (response.ok) {
      healthy = true;
      break;
    }
  } catch {}
  await new Promise((resolve) => setTimeout(resolve, 500));
}

if (!healthy) {
  if (!stopping) console.error("FastAPI did not become healthy within 90 seconds.");
  stop(1);
} else if (!stopping) {
  const pnpm = windows ? "pnpm.cmd" : "pnpm";
  start(
    "ShopSense web app",
    pnpm,
    ["--filter", "@workspace/shopsense", "run", "dev"],
    {
      cwd: root,
      env: {
        ...process.env,
        PORT: webPort,
        BASE_PATH: "/shopsense/",
        SHOPSENSE_BACKEND_URL: `http://127.0.0.1:${apiPort}`,
      },
    },
  );
  console.log(`\nOpen http://localhost:${webPort}/shopsense/ in your browser. Press Ctrl+C to stop.`);
}
