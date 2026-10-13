export interface LockEntry { url: string; md5: string; size: number }
export function verify(dir: string, lock: Record<string, LockEntry>): { missing: string[]; bad: string[] };
