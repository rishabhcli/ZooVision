import { spawn } from "node:child_process";
import { createConnection } from "node:net";
import { fileURLToPath } from "node:url";

const projectRoot = fileURLToPath(new URL("..", import.meta.url));
const host = "127.0.0.1";
const children = new Set();
let shuttingDown = false;

function requestedPort(name, fallback) {
  const value = Number.parseInt(process.env[name] ?? "", 10);
  return Number.isInteger(value) && value > 0 && value < 65536 ? value : fallback;
}

function portIsListening(port, address) {
  return new Promise((resolve) => {
    const socket = createConnection({ port, host: address });
    const finish = (listening) => {
      socket.destroy();
      resolve(listening);
    };
    socket.setTimeout(250, () => finish(false));
    socket.once("connect", () => finish(true));
    socket.once("error", () => finish(false));
  });
}

async function portIsAvailable(port) {
  const [ipv4, ipv6] = await Promise.all([
    portIsListening(port, "127.0.0.1"),
    portIsListening(port, "::1"),
  ]);
  return !ipv4 && !ipv6;
}

async function findAvailablePort(start) {
  for (let port = start; port < start + 100; port += 1) {
    if (await portIsAvailable(port)) return port;
  }
  throw new Error(`No free port found between ${start} and ${start + 99}`);
}

function start(command, args, options = {}) {
  const child = spawn(command, args, {
    cwd: projectRoot,
    detached: process.platform !== "win32",
    env: { ...process.env, ...options.env },
    stdio: "inherit",
  });
  children.add(child);
  child.once("error", (error) => {
    console.error(`Unable to start ${command}: ${error.message}`);
    void shutdown(1);
  });
  child.once("exit", (code, signal) => {
    children.delete(child);
    if (!shuttingDown) {
      console.error(`${command} stopped unexpectedly (${signal ?? code ?? "unknown"}).`);
      void shutdown(code || 1);
    }
  });
  return child;
}

async function waitFor(url, label, timeoutMs = 60_000) {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      const response = await fetch(url);
      if (response.ok) return;
    } catch {
      // The service is still starting.
    }
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`${label} did not become ready within ${timeoutMs / 1000} seconds`);
}

function stop(child, signal) {
  if (!child.pid || child.exitCode !== null) return;
  try {
    if (process.platform === "win32") {
      child.kill(signal);
    } else {
      process.kill(-child.pid, signal);
    }
  } catch {
    // The process may have exited between the status check and the signal.
  }
}

async function shutdown(exitCode = 0) {
  if (shuttingDown) return;
  shuttingDown = true;
  for (const child of children) stop(child, "SIGTERM");
  await new Promise((resolve) => setTimeout(resolve, 500));
  for (const child of children) stop(child, "SIGKILL");
  process.exit(exitCode);
}

process.once("SIGINT", () => void shutdown(0));
process.once("SIGTERM", () => void shutdown(0));

try {
  const apiPort = await findAvailablePort(requestedPort("ZOOVISION_API_PORT", 8000));
  const webPort = await findAvailablePort(requestedPort("ZOOVISION_WEB_PORT", 3000));
  const apiOrigin = `http://${host}:${apiPort}`;
  const webOrigin = `http://localhost:${webPort}`;

  start("uv", [
    "run",
    "uvicorn",
    "zoovision.api:app",
    "--app-dir",
    "backend",
    "--host",
    host,
    "--port",
    String(apiPort),
  ], {
    env: {
      // dev:all must stay a local fixture workflow even when the checkout's
      // ignored .env contains production credentials and policies.
      ZOOVISION_ENV: "development",
      ZOOVISION_FIXTURE_MODE: "true",
      ZOOVISION_OPERATOR_IDENTITY_REQUIRED: "false",
      TWELVELABS_API_KEY: "",
    },
  });
  await waitFor(`${apiOrigin}/api/health`, "ZooVision API");

  start(
    "npm",
    ["run", "dev", "--", "--host", host, "--port", String(webPort)],
    { env: { ZOOVISION_API_ORIGIN: apiOrigin } },
  );
  await waitFor(`${webOrigin}/monitor`, "ZooVision UI");

  console.log(`\nZooVision is ready: ${webOrigin}`);
  console.log(`Backend: ${apiOrigin}`);
  console.log("Press Ctrl+C once to stop both services.\n");
} catch (error) {
  console.error(error instanceof Error ? error.message : error);
  await shutdown(1);
}
