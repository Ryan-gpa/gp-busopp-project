import { useState } from "react"
import { User, ArrowRight, Loader2 } from "lucide-react"
import type { CurrentUser } from "@/types"

interface Props {
  onSave: (user: CurrentUser) => void
  apiBase: string
}

export default function UserIdentityModal({ onSave, apiBase }: Props) {
  const [displayName, setDisplayName] = useState("")
  const [email, setEmail] = useState("")
  const [saving, setSaving] = useState(false)
  const [error, setError] = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    const name = displayName.trim()
    const mail = email.trim().toLowerCase()
    if (!name || !mail) { setError("Both fields are required."); return }
    if (!mail.includes("@")) { setError("Please enter a valid email address."); return }
    setSaving(true)
    setError("")
    try {
      const res = await fetch(`${apiBase}/api/users/register`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email: mail, displayName: name }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      onSave({ userId: data.userId, displayName: data.displayName })
    } catch (err) {
      setError(`Could not register: ${err instanceof Error ? err.message : String(err)}`)
      setSaving(false)
    }
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 backdrop-blur-sm">
      <div className="bg-card border border-border rounded-sm shadow-xl w-full max-w-sm mx-4 p-6 space-y-5">
        <div className="space-y-1">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-full bg-accent/10 flex items-center justify-center shrink-0">
              <User className="w-4 h-4 text-accent" />
            </div>
            <h2 className="font-heading font-semibold text-base text-foreground">Set up your profile</h2>
          </div>
          <p className="text-xs text-muted-foreground pl-10">
            Your name appears on votes and annotations you leave across announcements — visible to the whole team.
          </p>
        </div>

        <form onSubmit={handleSubmit} className="space-y-3">
          <div className="space-y-1">
            <label className="block text-xs font-medium text-foreground">Display name</label>
            <input
              type="text"
              value={displayName}
              onChange={(e) => setDisplayName(e.target.value)}
              placeholder="e.g. Ryan"
              autoFocus
              className="w-full h-9 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>
          <div className="space-y-1">
            <label className="block text-xs font-medium text-foreground">Work email</label>
            <input
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="you@growthpartnersadvisory.com"
              className="w-full h-9 px-3 text-sm border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
            />
          </div>

          {error && (
            <p className="text-xs text-destructive bg-destructive/10 px-3 py-2 rounded-sm">{error}</p>
          )}

          <button
            type="submit"
            disabled={saving}
            className="w-full h-9 flex items-center justify-center gap-2 bg-accent hover:bg-accent/90 text-white text-sm font-medium rounded-sm transition-colors disabled:opacity-50"
          >
            {saving ? <Loader2 className="w-4 h-4 animate-spin" /> : <ArrowRight className="w-4 h-4" />}
            {saving ? "Setting up…" : "Get started"}
          </button>
        </form>
      </div>
    </div>
  )
}
