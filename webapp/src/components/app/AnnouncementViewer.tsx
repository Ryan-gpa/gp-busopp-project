import { useState, useEffect, useRef } from "react"
import { X, Loader2, Save, FileText, FileSearch, Sparkles } from "lucide-react"
import { Button } from "@/components/ui/button"
import type { AsxItem, ResultItem } from "@/types"

interface Props {
  announcement: AsxItem
  checklistItems: ResultItem[]
  onClose: () => void
}

const OPPORTUNITY_RULES = [
  { id: "ma_transaction", label: "M&A / Transaction (Transaction Readiness)" },
  { id: "capital_raise", label: "Capital Raise / Debt (Transaction Readiness + Financial Reporting)" },
  { id: "earnings_guidance", label: "Earnings / Guidance (Commercial Opportunities + Financial Reporting)" },
  { id: "periodic_reporting", label: "Periodic Reporting / Audit (Financial Reporting + Audit Readiness)" },
  { id: "cfo_finance_lead", label: "CFO / Finance Lead Change (Financial Reporting + Business Process Redesign)" },
  { id: "market_status", label: "Market Status (Trading Halt/Suspension)" },
  { id: "cross_border", label: "Cross Border / Delisting" },
  { id: "reporting_other", label: "Reporting Other (NTA, Sustainability)" },
  { id: "leadership_change", label: "Leadership Change (CEO, Chair)" },
  { id: "ownership_board", label: "Ownership / Board Change" },
  { id: "legal_regulatory", label: "Legal / Regulatory (Litigation, ASX Query)" },
  { id: "governance_auditor", label: "Governance / Auditor Change" },
  { id: "operational_milestone", label: "Operational / Scaling Milestone" },
  { id: "buyback_capital", label: "Buy-backs (Advisory)" },
  { id: "routine_admin", label: "Routine / Administrative (Cleansing, proxy)" },
]

export default function AnnouncementViewer({ announcement, checklistItems, onClose }: Props) {
  const API_BASE = import.meta.env.VITE_API_URL || ""
  const [activeTab, setActiveTab] = useState<"pdf" | "text">("pdf")
  const [text, setText] = useState<string>("")
  const [loadingText, setLoadingText] = useState(false)
  const [textError, setTextError] = useState("")

  const [selectedText, setSelectedText] = useState("")
  const [saveType, setSaveType] = useState<"customRule" | "checklist" | "opportunity">("customRule")
  const [selectedTargetId, setSelectedTargetId] = useState("")
  const [savingKeyword, setSavingKeyword] = useState(false)
  const [saveStatus, setSaveStatus] = useState<{ type: "success" | "error"; msg: string } | null>(null)
  const [customAction, setCustomAction] = useState<"include" | "exclude">("exclude")
  const [announcementTypeInput, setAnnouncementTypeInput] = useState("")
  const [votingState, setVotingState] = useState<"idle" | "saving" | "done">("idle")
  const [voteResult, setVoteResult] = useState<"up" | "down" | null>(null)
  const [showAdvanced, setShowAdvanced] = useState(false)

  const textContainerRef = useRef<HTMLDivElement>(null)

  // Fetch text when announcement changes and text tab is active
  useEffect(() => {
    if (!announcement.documentKey) return
    setLoadingText(true)
    setText("")
    setTextError("")
    setSelectedText("")
    setSaveStatus(null)
    setAnnouncementTypeInput(announcement.type || "")

    fetch(`${API_BASE}/api/announcement-text/${announcement.documentKey}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`)
        return res.json()
      })
      .then((data) => {
        setText(data.text || "No text could be extracted from this document.")
      })
      .catch((err) => {
        setTextError(err instanceof Error ? err.message : String(err))
      })
      .finally(() => {
        setLoadingText(false)
      })
  }, [announcement.documentKey])

  // Handle text selection
  const handleTextSelection = () => {
    const selection = window.getSelection()
    if (selection) {
      const selected = selection.toString().trim()
      if (selected && selected.length < 150) {
        setSelectedText(selected)
        setSaveStatus(null)
        // Auto-select first target if not already set
        if (!selectedTargetId) {
          if (saveType === "checklist" && checklistItems.length > 0) {
            setSelectedTargetId(checklistItems[0].id)
          } else if (saveType === "opportunity" && OPPORTUNITY_RULES.length > 0) {
            setSelectedTargetId(OPPORTUNITY_RULES[0].id)
          }
        }
      }
    }
  }

  // Update dropdown target when switching save type
  useEffect(() => {
    if (saveType === "checklist" && checklistItems.length > 0) {
      setSelectedTargetId(checklistItems[0].id)
    } else if (saveType === "opportunity" && OPPORTUNITY_RULES.length > 0) {
      setSelectedTargetId(OPPORTUNITY_RULES[0].id)
    }
  }, [saveType, checklistItems])

  const handleVote = async (vote: "up" | "down") => {
    if (!selectedText) return
    setVotingState("saving")
    try {
      await fetch(`${API_BASE}/api/votes`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: selectedText,
          vote,
          documentKey: announcement.documentKey ?? "",
          headline: announcement.headline,
          announcementType: announcement.type,
        }),
      })
      setVoteResult(vote)
      setVotingState("done")
      setTimeout(() => {
        setSelectedText("")
        setVotingState("idle")
        setVoteResult(null)
        setShowAdvanced(false)
      }, 1800)
    } catch {
      setVotingState("idle")
    }
  }

  const handleSaveKeyword = async () => {
    if (!selectedText) return
    if (saveType !== "customRule" && !selectedTargetId) return
    setSavingKeyword(true)
    setSaveStatus(null)

    let endpoint = ""
    let payload = {}

    if (saveType === "checklist") {
      endpoint = "/api/checklist/add-keyword"
      payload = { itemId: selectedTargetId, keyword: selectedText }
    } else if (saveType === "opportunity") {
      endpoint = "/api/opportunity/add-keyword"
      payload = { ruleId: selectedTargetId, keyword: selectedText }
    } else {
      endpoint = "/api/announcement-rules/add"
      payload = {
        announcementType: announcementTypeInput || announcement.type || "",
        text: selectedText,
        action: customAction,
      }
    }

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      await res.json()
      setSaveStatus({
        type: "success",
        msg: saveType === "customRule"
          ? `Saved custom ${customAction} override rule successfully!`
          : `Added phrase to memory! It will apply to future reviews.`,
      })
      // Clear selection after a delay
      setTimeout(() => {
        setSelectedText("")
        setSaveStatus(null)
      }, 3000)
    } catch (err) {
      setSaveStatus({
        type: "error",
        msg: `Failed to save: ${err instanceof Error ? err.message : String(err)}`,
      })
    } finally {
      setSavingKeyword(false)
    }
  }

  const pdfUrl = announcement.documentKey
    ? `${API_BASE}/api/announcement/${announcement.documentKey}?t=${new Date().getTime()}`
    : ""

  return (
    <div className="bg-card border border-border rounded-sm shadow-xl flex flex-col h-[calc(100vh-140px)] overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border bg-muted/20 flex items-center justify-between shrink-0">
        <div className="min-w-0 flex-1 pr-4">
          <h3 className="font-heading font-medium text-sm text-foreground truncate" title={announcement.headline}>
            {announcement.headline}
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            {announcement.type} &middot; {new Date(announcement.date).toLocaleDateString("en-AU")}
          </p>
        </div>
        <button
          onClick={onClose}
          className="p-1 rounded-sm hover:bg-muted text-muted-foreground hover:text-foreground transition-colors shrink-0"
        >
          <X className="w-4 h-4" />
        </button>
      </div>

      {/* Tabs list */}
      <div className="flex border-b border-border bg-muted/10 shrink-0">
        <button
          onClick={() => setActiveTab("pdf")}
          className={`flex-1 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            activeTab === "pdf"
              ? "border-accent text-accent bg-background"
              : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30"
          }`}
        >
          <FileText className="w-3.5 h-3.5" />
          PDF View
        </button>
        <button
          onClick={() => setActiveTab("text")}
          className={`flex-1 py-2 text-xs font-semibold border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
            activeTab === "text"
              ? "border-accent text-accent bg-background"
              : "border-transparent text-muted-foreground hover:text-foreground hover:bg-muted/30"
          }`}
        >
          <FileSearch className="w-3.5 h-3.5" />
          Extracted Text
        </button>
      </div>

      {/* Content Area */}
      <div className="flex-1 min-h-0 relative flex flex-col">
        {activeTab === "pdf" ? (
          pdfUrl ? (
            <iframe
              src={pdfUrl}
              className="w-full h-full border-none"
              title="Announcement PDF"
            />
          ) : (
            <div className="flex items-center justify-center h-full text-muted-foreground text-sm">
              No document URL available.
            </div>
          )
        ) : (
          <div className="flex flex-col h-full min-h-0">
            {/* Scrollable Text container */}
            <div className="flex-1 overflow-y-auto px-4 py-3 min-h-0">
              {loadingText ? (
                <div className="flex flex-col items-center justify-center h-full space-y-2 text-muted-foreground">
                  <Loader2 className="w-6 h-6 animate-spin text-accent" />
                  <span className="text-xs">Extracting text via pdfplumber...</span>
                </div>
              ) : textError ? (
                <div className="p-3 rounded-sm bg-destructive/10 text-destructive text-xs">
                  {textError}
                </div>
              ) : (
                <div
                  ref={textContainerRef}
                  onMouseUp={handleTextSelection}
                  className="text-xs font-sans whitespace-pre-wrap leading-relaxed select-text cursor-text text-foreground"
                >
                  {text}
                </div>
              )}
            </div>

            {/* Selection panel */}
            {selectedText && (
              <div className="border-t border-border bg-muted/40 px-4 py-3 shrink-0 space-y-3">

                {/* Selected text preview */}
                <p className="font-mono text-xs bg-background border border-border rounded-sm px-2 py-1.5 truncate text-foreground">
                  "{selectedText}"
                </p>

                {/* Vote buttons / confirmation */}
                {votingState === "done" ? (
                  <div className={`text-xs px-3 py-2 rounded-sm font-medium text-center ${
                    voteResult === "up" ? "bg-[#C6E0B4] text-[#375623]" : "bg-muted text-muted-foreground"
                  }`}>
                    {voteResult === "up" ? "👍 Flagged for closer review" : "👎 Marked as less relevant"}
                  </div>
                ) : (
                  <div className="flex items-center gap-2">
                    <button
                      onClick={() => handleVote("up")}
                      disabled={votingState === "saving"}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-sm border border-[#375623]/30 bg-[#C6E0B4]/20 hover:bg-[#C6E0B4]/50 text-[#375623] text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      {votingState === "saving" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "👍"}
                      Needs closer review
                    </button>
                    <button
                      onClick={() => handleVote("down")}
                      disabled={votingState === "saving"}
                      className="flex-1 flex items-center justify-center gap-2 px-3 py-2 rounded-sm border border-border bg-muted/30 hover:bg-muted/60 text-muted-foreground text-xs font-medium transition-colors disabled:opacity-50"
                    >
                      {votingState === "saving" ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : "👎"}
                      Less relevant
                    </button>
                    <button
                      onClick={() => { setSelectedText(""); setShowAdvanced(false) }}
                      className="px-2 py-2 text-xs text-muted-foreground hover:text-foreground transition-colors"
                    >
                      ✕
                    </button>
                  </div>
                )}

                {/* Advanced: save to memory (collapsed by default) */}
                {votingState !== "done" && (
                  <div>
                    <button
                      onClick={() => setShowAdvanced(v => !v)}
                      className="text-[11px] text-muted-foreground hover:text-foreground transition-colors flex items-center gap-1"
                    >
                      <Sparkles className="w-3 h-3" />
                      {showAdvanced ? "Hide" : "Advanced"}: save phrase to memory
                    </button>

                    {showAdvanced && (
                      <div className="mt-2 space-y-2 pt-2 border-t border-border">
                        <div className="grid grid-cols-3 gap-2">
                          {(["customRule", "checklist", "opportunity"] as const).map((t) => (
                            <label key={t} className="flex items-center gap-1 text-[11px] cursor-pointer font-medium">
                              <input type="radio" name="saveType" checked={saveType === t} onChange={() => setSaveType(t)} />
                              {t === "customRule" ? "Search Override" : t === "checklist" ? "Checklist Keyword" : "Opportunity Match"}
                            </label>
                          ))}
                        </div>

                        {saveType === "customRule" ? (
                          <div className="space-y-2">
                            <input
                              type="text"
                              value={announcementTypeInput}
                              onChange={(e) => setAnnouncementTypeInput(e.target.value)}
                              className="w-full h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                              placeholder="Announcement type (e.g. Proposed issue of securities)"
                            />
                            <div className="flex gap-4">
                              {(["include", "exclude"] as const).map((a) => (
                                <label key={a} className={`flex items-center gap-1.5 text-xs cursor-pointer font-medium ${a === "include" ? "text-[#375623]" : "text-[#9C0006]"}`}>
                                  <input type="radio" name="customAction" checked={customAction === a} onChange={() => setCustomAction(a)} />
                                  {a === "include" ? "Include (RAG GREEN)" : "Exclude (RAG RED)"}
                                </label>
                              ))}
                            </div>
                          </div>
                        ) : (
                          <select
                            value={selectedTargetId}
                            onChange={(e) => setSelectedTargetId(e.target.value)}
                            className="w-full h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                          >
                            {saveType === "checklist"
                              ? checklistItems.map((item) => (
                                  <option key={item.id} value={item.id}>{item.standard} · {item.title}</option>
                                ))
                              : OPPORTUNITY_RULES.map((rule) => (
                                  <option key={rule.id} value={rule.id}>{rule.label}</option>
                                ))}
                          </select>
                        )}

                        {saveStatus && (
                          <div className={`text-xs p-2 rounded-sm ${saveStatus.type === "success" ? "bg-[#C6E0B4] text-[#375623]" : "bg-[#FFC7CE] text-[#9C0006]"}`}>
                            {saveStatus.msg}
                          </div>
                        )}

                        <div className="flex justify-end">
                          <Button
                            onClick={handleSaveKeyword}
                            disabled={savingKeyword || (saveType !== "customRule" && !selectedTargetId)}
                            size="sm"
                            className="text-xs h-8 bg-accent hover:bg-accent/90 flex items-center gap-1.5"
                          >
                            {savingKeyword ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <Save className="w-3.5 h-3.5" />}
                            Save to memory
                          </Button>
                        </div>
                      </div>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
