import { useState, useEffect, useMemo } from "react"
import { useNavigate } from "react-router-dom"
import { ArrowLeft, ThumbsUp, ThumbsDown, Loader2, Filter } from "lucide-react"
import type { VotePhrase } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL || ""

function ScoreBar({ upvotes, downvotes }: { upvotes: number; downvotes: number }) {
  const total = upvotes + downvotes
  if (total === 0) return <span className="text-xs text-muted-foreground">—</span>
  const pct = Math.round((upvotes / total) * 100)
  return (
    <div className="flex items-center gap-2 min-w-[120px]">
      <div className="flex-1 h-1.5 bg-muted rounded-full overflow-hidden">
        <div className="h-full bg-[#375623] rounded-full" style={{ width: `${pct}%` }} />
      </div>
      <span className="text-[11px] text-muted-foreground whitespace-nowrap">
        {upvotes}↑ {downvotes}↓
      </span>
    </div>
  )
}

function VoterPills({ phrase, highlightUserId }: { phrase: VotePhrase; highlightUserId?: string }) {
  return (
    <div className="flex flex-wrap gap-1">
      {phrase.votes.map(v => (
        <span
          key={v.userId}
          className={`inline-flex items-center gap-0.5 text-[10px] px-1.5 py-0.5 rounded-full border ${
            v.vote === "up"
              ? "bg-[#C6E0B4]/50 border-[#375623]/30 text-[#375623]"
              : "bg-muted border-border text-muted-foreground"
          } ${v.userId === highlightUserId ? "ring-1 ring-accent" : ""}`}
        >
          {v.vote === "up" ? "👍" : "👎"} {v.displayName}
        </span>
      ))}
    </div>
  )
}

export default function VotesPage() {
  const navigate = useNavigate()
  const [phrases, setPhrases] = useState<VotePhrase[]>([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState("")
  const [typeFilter, setTypeFilter] = useState("all")
  const [voteFilter, setVoteFilter] = useState<"all" | "up" | "down">("all")
  const [sort, setSort] = useState<"score" | "recent" | "activity">("score")
  const [view, setView] = useState<"phrases" | "timeline">("phrases")

  useEffect(() => {
    fetch(`${API_BASE}/api/votes`)
      .then(r => r.ok ? r.json() : Promise.reject(`HTTP ${r.status}`))
      .then(data => setPhrases(data.phrases || []))
      .catch(e => setError(String(e)))
      .finally(() => setLoading(false))
  }, [])

  const announcementTypes = useMemo(() => {
    const types = new Set(phrases.map(p => p.announcementType).filter(Boolean))
    return ["all", ...Array.from(types).sort()]
  }, [phrases])

  const filtered = useMemo(() => {
    let list = phrases.filter(p => p.votes.length > 0)
    if (typeFilter !== "all") list = list.filter(p => p.announcementType === typeFilter)
    if (voteFilter === "up") list = list.filter(p => p.score > 0)
    if (voteFilter === "down") list = list.filter(p => p.score < 0)
    if (sort === "score") list = [...list].sort((a, b) => b.score - a.score)
    if (sort === "recent") {
      list = [...list].sort((a, b) => {
        const aLatest = Math.max(...a.votes.map(v => new Date(v.votedAt).getTime()))
        const bLatest = Math.max(...b.votes.map(v => new Date(v.votedAt).getTime()))
        return bLatest - aLatest
      })
    }
    if (sort === "activity") list = [...list].sort((a, b) => b.votes.length - a.votes.length)
    return list
  }, [phrases, typeFilter, voteFilter, sort])

  // Timeline: all individual vote events sorted by time
  const timeline = useMemo(() => {
    const events: Array<{ phrase: VotePhrase; userId: string; displayName: string; vote: "up" | "down"; votedAt: string }> = []
    for (const phrase of phrases) {
      for (const v of phrase.votes) {
        events.push({ phrase, userId: v.userId, displayName: v.displayName, vote: v.vote, votedAt: v.votedAt })
      }
    }
    return events.sort((a, b) => new Date(b.votedAt).getTime() - new Date(a.votedAt).getTime())
  }, [phrases])

  // Stats
  const totalVoteEvents = phrases.reduce((s, p) => s + p.votes.length, 0)
  const topType = useMemo(() => {
    const counts: Record<string, number> = {}
    for (const p of phrases) {
      if (p.announcementType) counts[p.announcementType] = (counts[p.announcementType] || 0) + p.votes.length
    }
    return Object.entries(counts).sort((a, b) => b[1] - a[1])[0]?.[0] ?? "—"
  }, [phrases])
  const uniqueVoters = useMemo(() => {
    const ids = new Set<string>()
    phrases.forEach(p => p.votes.forEach(v => ids.add(v.userId)))
    return ids.size
  }, [phrases])

  return (
    <div className="min-h-screen bg-background">
      {/* Header */}
      <header className="bg-[hsl(var(--navy-deep))] text-primary-foreground px-6 py-4 flex items-center gap-4">
        <button onClick={() => navigate(-1)} className="flex items-center gap-1.5 text-sm opacity-70 hover:opacity-100 transition-opacity">
          <ArrowLeft className="w-4 h-4" />
          Back
        </button>
        <h1 className="font-heading font-semibold text-lg">Vote History</h1>
        <span className="text-xs opacity-50 ml-auto">All sessions · All announcements</span>
      </header>

      <main className="max-w-5xl mx-auto px-6 py-8 space-y-6">

        {/* Stats row */}
        <div className="grid grid-cols-3 gap-4">
          {[
            { label: "Phrases voted", value: phrases.filter(p => p.votes.length > 0).length },
            { label: "Total vote events", value: totalVoteEvents },
            { label: "Unique voters", value: uniqueVoters },
          ].map(s => (
            <div key={s.label} className="bg-card border border-border rounded-sm px-4 py-3">
              <p className="text-2xl font-heading font-bold text-foreground">{s.value}</p>
              <p className="text-xs text-muted-foreground mt-0.5">{s.label}</p>
            </div>
          ))}
        </div>

        {topType !== "—" && (
          <p className="text-xs text-muted-foreground">
            Most voted announcement type: <span className="font-medium text-foreground">{topType}</span>
          </p>
        )}

        {/* View toggle */}
        <div className="flex items-center gap-2 border-b border-border pb-3">
          {(["phrases", "timeline"] as const).map(v => (
            <button
              key={v}
              onClick={() => setView(v)}
              className={`text-xs font-semibold px-3 py-1.5 rounded-sm transition-colors ${
                view === v ? "bg-accent text-white" : "text-muted-foreground hover:text-foreground"
              }`}
            >
              {v === "phrases" ? "By phrase" : "Timeline"}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="flex justify-center py-16 text-muted-foreground">
            <Loader2 className="w-6 h-6 animate-spin" />
          </div>
        ) : error ? (
          <div className="text-sm text-destructive bg-destructive/10 px-4 py-3 rounded-sm">{error}</div>
        ) : view === "phrases" ? (
          <>
            {/* Filters */}
            <div className="flex flex-wrap gap-3 items-end">
              <div>
                <label className="block text-[10px] uppercase font-semibold text-muted-foreground mb-1 tracking-wide">
                  <Filter className="w-3 h-3 inline mr-1" />Type
                </label>
                <select
                  value={typeFilter}
                  onChange={e => setTypeFilter(e.target.value)}
                  className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none"
                >
                  {announcementTypes.map(t => <option key={t} value={t}>{t === "all" ? "All types" : t}</option>)}
                </select>
              </div>
              <div>
                <label className="block text-[10px] uppercase font-semibold text-muted-foreground mb-1 tracking-wide">Direction</label>
                <select
                  value={voteFilter}
                  onChange={e => setVoteFilter(e.target.value as typeof voteFilter)}
                  className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none"
                >
                  <option value="all">All</option>
                  <option value="up">Net positive only</option>
                  <option value="down">Net negative only</option>
                </select>
              </div>
              <div>
                <label className="block text-[10px] uppercase font-semibold text-muted-foreground mb-1 tracking-wide">Sort</label>
                <select
                  value={sort}
                  onChange={e => setSort(e.target.value as typeof sort)}
                  className="h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none"
                >
                  <option value="score">Highest score</option>
                  <option value="recent">Most recently voted</option>
                  <option value="activity">Most votes</option>
                </select>
              </div>
              <span className="text-xs text-muted-foreground self-end pb-1">{filtered.length} phrase{filtered.length !== 1 ? "s" : ""}</span>
            </div>

            {filtered.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-16">No votes recorded yet.</p>
            ) : (
              <div className="overflow-x-auto rounded-sm border border-border">
                <table className="w-full text-sm">
                  <thead>
                    <tr className="bg-[hsl(var(--navy-deep))] text-primary-foreground">
                      <th className="text-left px-4 py-2.5 text-xs font-medium">Phrase</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium w-44">Type</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium w-36">Score</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium">Voters</th>
                      <th className="text-left px-4 py-2.5 text-xs font-medium w-28">Last voted</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-border">
                    {filtered.map(phrase => {
                      const lastVoted = phrase.votes.length
                        ? new Date(Math.max(...phrase.votes.map(v => new Date(v.votedAt).getTime())))
                        : null
                      return (
                        <tr key={phrase.id} className="hover:bg-muted/30">
                          <td className="px-4 py-3 align-top">
                            <p className="font-mono text-xs text-foreground leading-snug max-w-xs break-words">
                              "{phrase.text}"
                            </p>
                            {phrase.headline && (
                              <p className="text-[10px] text-muted-foreground mt-0.5 truncate max-w-xs" title={phrase.headline}>
                                {phrase.headline}
                              </p>
                            )}
                          </td>
                          <td className="px-4 py-3 align-top">
                            <span className="text-xs text-muted-foreground">{phrase.announcementType || "—"}</span>
                          </td>
                          <td className="px-4 py-3 align-top">
                            <div className="flex items-center gap-1.5 mb-1">
                              {phrase.score > 0
                                ? <ThumbsUp className="w-3.5 h-3.5 text-[#375623]" />
                                : phrase.score < 0
                                ? <ThumbsDown className="w-3.5 h-3.5 text-muted-foreground" />
                                : null}
                              <span className={`text-sm font-bold ${phrase.score > 0 ? "text-[#375623]" : phrase.score < 0 ? "text-muted-foreground" : "text-foreground"}`}>
                                {phrase.score > 0 ? `+${phrase.score}` : phrase.score}
                              </span>
                            </div>
                            <ScoreBar upvotes={phrase.upvotes} downvotes={phrase.downvotes} />
                          </td>
                          <td className="px-4 py-3 align-top">
                            <VoterPills phrase={phrase} />
                          </td>
                          <td className="px-4 py-3 align-top">
                            <span className="text-xs text-muted-foreground">
                              {lastVoted ? lastVoted.toLocaleDateString("en-AU", { day: "2-digit", month: "short", year: "numeric" }) : "—"}
                            </span>
                          </td>
                        </tr>
                      )
                    })}
                  </tbody>
                </table>
              </div>
            )}
          </>
        ) : (
          /* Timeline view */
          <div className="space-y-1">
            {timeline.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-16">No votes recorded yet.</p>
            ) : (
              timeline.map((event, i) => (
                <div key={i} className="flex items-start gap-3 px-3 py-2.5 rounded-sm hover:bg-muted/30">
                  <span className={`mt-0.5 text-base leading-none`}>
                    {event.vote === "up" ? "👍" : "👎"}
                  </span>
                  <div className="flex-1 min-w-0">
                    <p className="text-xs font-mono text-foreground truncate">"{event.phrase.text}"</p>
                    <p className="text-[10px] text-muted-foreground mt-0.5">
                      {event.phrase.announcementType} · {event.phrase.headline}
                    </p>
                  </div>
                  <div className="text-right shrink-0">
                    <p className="text-xs font-medium text-foreground">{event.displayName}</p>
                    <p className="text-[10px] text-muted-foreground">
                      {new Date(event.votedAt).toLocaleDateString("en-AU", { day: "2-digit", month: "short" })}{" "}
                      {new Date(event.votedAt).toLocaleTimeString("en-AU", { hour: "2-digit", minute: "2-digit" })}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </main>
    </div>
  )
}
