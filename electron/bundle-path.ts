export const genomeBundlePickerExtensions = ["gz", "tar"];

const genomeBundleSuffixes = [".genome.tar.gz", ".genome.tar"];

export function isGenomeBundlePath(filePath: string): boolean {
  const normalized = filePath.toLowerCase();
  return genomeBundleSuffixes.some((suffix) => normalized.endsWith(suffix));
}
