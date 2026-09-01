const { readdirSync } = require("node:fs");
const path = require("node:path");
const { spawnSync } = require("node:child_process");

function run(command, args) {
  const result = spawnSync(command, args, { encoding: "utf8" });
  if (result.status !== 0) {
    throw new Error(
      `${command} ${args.join(" ")} failed:\n${result.stderr || result.stdout}`,
    );
  }
}

exports.default = async function refreshAdHocMacSignature(context) {
  if (context.electronPlatformName !== "darwin") return;
  if (context.packager.platformSpecificBuildOptions.identity !== "-") return;

  const appNames = readdirSync(context.appOutDir).filter((name) => name.endsWith(".app"));
  if (appNames.length !== 1) {
    throw new Error("Expected exactly one macOS app before ad-hoc signing.");
  }
  const appPath = path.join(context.appOutDir, appNames[0]);
  run("codesign", ["--force", "--deep", "--sign", "-", "--timestamp=none", appPath]);
  run("codesign", ["--verify", "--deep", "--strict", "--verbose=2", appPath]);
};
