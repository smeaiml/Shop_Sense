import { spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..");
const windows = process.platform === "win32";
const shell = windows;
const pythonCommand = process.env.PYTHON || (windows ? "py" : "python3");
const pythonPrefix = process.env.PYTHON ? [] : windows ? ["-3"] : [];
const pythonInVenv = windows
  ? path.join(root, ".venv", "Scripts", "python.exe")
  : path.join(root, ".venv", "bin", "python");

function run(command, args, label) {
  console.log(`\n==> ${label}`);
  const result = spawnSync(command, args, {
    cwd: root,
    stdio: "inherit",
    shell,
    env: process.env,
  });
  if (result.error) {
    console.error(result.error.message);
    process.exit(1);
  }
  if (result.status !== 0) {
    process.exit(result.status ?? 1);
  }
}

run(pythonCommand, [...pythonPrefix, "-m", "venv", ".venv"], "Create Python environment");
run(windows ? "pnpm.cmd" : "pnpm", ["install"], "Install web dependencies");
run(pythonInVenv, ["-m", "pip", "install", "--upgrade", "pip"], "Update pip");
run(
  pythonInVenv,
  ["-m", "pip", "install", "-e", "artifacts/shopsense/backend[dev]"],
  "Install ShopSense backend and test dependencies",
);

console.log("\nSetup is complete. Run the task “ShopSense: Run Local Demo” in VS Code.");
