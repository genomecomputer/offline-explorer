import { constants, setPriority } from "node:os";

type PrioritySetter = (pid: number, priority: number) => void;

export function lowerProcessPriority(
  pid: number | undefined,
  prioritySetter: PrioritySetter = setPriority,
): boolean {
  if (!Number.isSafeInteger(pid) || (pid ?? 0) <= 0) return false;
  try {
    prioritySetter(pid as number, constants.priority.PRIORITY_BELOW_NORMAL);
    return true;
  } catch {
    return false;
  }
}
