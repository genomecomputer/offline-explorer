import {
  existsSync,
  lstatSync,
  mkdirSync,
  renameSync,
} from "node:fs";
import path from "node:path";

const legacyApplicationName = "Genome Explorer";
const appOwnedData = [
  { name: "workspaces", kind: "directory" },
  { name: "bundle-library.json", kind: "file" },
  { name: "saved-results.json", kind: "file" },
] as const;

export function migrateLegacyUserData(currentUserData: string): string[] {
  const current = path.resolve(currentUserData);
  const legacy = path.join(path.dirname(current), legacyApplicationName);
  if (legacy === current || !existsSync(legacy)) return [];

  const migrated: string[] = [];
  for (const item of appOwnedData) {
    const source = path.join(legacy, item.name);
    const destination = path.join(current, item.name);
    if (!existsSync(source) || existsSync(destination)) continue;
    try {
      const metadata = lstatSync(source);
      const expectedType = item.kind === "directory"
        ? metadata.isDirectory()
        : metadata.isFile();
      if (metadata.isSymbolicLink() || !expectedType) continue;
      mkdirSync(current, { recursive: true, mode: 0o700 });
      renameSync(source, destination);
      migrated.push(item.name);
    } catch {
      // The legacy data remains in place and can be retried on the next launch.
    }
  }
  return migrated;
}
