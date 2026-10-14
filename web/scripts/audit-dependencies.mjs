import { spawnSync } from "node:child_process";

const BLOCKING_SEVERITIES = new Set(["high", "critical"]);
const BRACES_GHSA = "GHSA-vfj7-8cjw-p6xm";

function runNpm(args) {
  const result = spawnSync("npm", args, {
    cwd: process.cwd(),
    encoding: "utf8",
    env: process.env,
  });

  if (!result.stdout.trim()) {
    throw new Error(
      `npm ${args.join(" ")} produced no JSON output. stderr: ${result.stderr}`,
    );
  }

  try {
    return JSON.parse(result.stdout);
  } catch (error) {
    throw new Error(
      `Failed to parse npm ${args.join(" ")} JSON output: ${error}. stdout: ${result.stdout}`,
    );
  }
}

function blockingNames(report) {
  return Object.entries(report.vulnerabilities ?? {})
    .filter(([, vulnerability]) =>
      BLOCKING_SEVERITIES.has(vulnerability.severity),
    )
    .map(([name]) => name)
    .sort();
}

function isAllowedBracesAdvisory(via) {
  return (
    typeof via === "object" &&
    via !== null &&
    via.name === "braces" &&
    BLOCKING_SEVERITIES.has(via.severity) &&
    typeof via.url === "string" &&
    via.url.includes(BRACES_GHSA)
  );
}

function onlyAllowedBracesChain(report, packageName, visiting = new Set()) {
  if (visiting.has(packageName)) {
    return true;
  }

  const vulnerability = report.vulnerabilities?.[packageName];
  if (!vulnerability || !BLOCKING_SEVERITIES.has(vulnerability.severity)) {
    return true;
  }

  const nextVisiting = new Set(visiting);
  nextVisiting.add(packageName);

  let sawBlockingCause = false;
  for (const via of vulnerability.via ?? []) {
    if (typeof via === "string") {
      const dependency = report.vulnerabilities?.[via];
      if (dependency && BLOCKING_SEVERITIES.has(dependency.severity)) {
        sawBlockingCause = true;
        if (!onlyAllowedBracesChain(report, via, nextVisiting)) {
          return false;
        }
      }
      continue;
    }

    if (via && BLOCKING_SEVERITIES.has(via.severity)) {
      sawBlockingCause = true;
      if (!isAllowedBracesAdvisory(via)) {
        return false;
      }
    }
  }

  return sawBlockingCause;
}

function containsDependency(tree, dependencyName) {
  const dependencies = tree?.dependencies ?? {};
  if (Object.prototype.hasOwnProperty.call(dependencies, dependencyName)) {
    return true;
  }
  return Object.values(dependencies).some((dependency) =>
    containsDependency(dependency, dependencyName),
  );
}

const productionAudit = runNpm(["audit", "--omit=dev", "--json"]);
const productionBlocking = blockingNames(productionAudit);
if (productionBlocking.length > 0) {
  console.error(
    "Production dependency audit contains blocking high/critical vulnerabilities:",
    productionBlocking,
  );
  process.exit(1);
}

const fullAudit = runNpm(["audit", "--json"]);
const fullBlocking = blockingNames(fullAudit);
const disallowed = fullBlocking.filter(
  (name) => !onlyAllowedBracesChain(fullAudit, name),
);

if (disallowed.length > 0) {
  console.error(
    "Dependency audit contains high/critical vulnerabilities outside the governed braces exception:",
    disallowed,
  );
  process.exit(1);
}

if (fullBlocking.length > 0) {
  const productionTree = runNpm([
    "ls",
    "braces",
    "--omit=dev",
    "--all",
    "--json",
  ]);
  if (containsDependency(productionTree, "braces")) {
    console.error(
      "Governed braces exception is invalid because braces is present in the production dependency tree.",
    );
    process.exit(1);
  }

  console.warn(
    `Accepted dev-only advisory ${BRACES_GHSA} for braces because upstream currently publishes no patched version. ` +
      "Exit condition: remove this exception immediately when a patched release or dependency path without braces becomes available.",
  );
}

console.log(
  "Dependency audit gate passed: production has no high/critical vulnerabilities; " +
    "full-tree high/critical findings are limited to the governed dev-only braces advisory.",
);
