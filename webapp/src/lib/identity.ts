import type { CurrentUser } from "@/types"

const KEY = "gp_disclosure_user"

export function getCurrentUser(): CurrentUser | null {
  try {
    const s = localStorage.getItem(KEY)
    return s ? (JSON.parse(s) as CurrentUser) : null
  } catch {
    return null
  }
}

export function saveCurrentUser(user: CurrentUser): void {
  localStorage.setItem(KEY, JSON.stringify(user))
}
