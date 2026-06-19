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
      const data = await res.json()
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

            {/* Selection Keyword Form */}
            {selectedText && (
              <div className="border-t border-border bg-muted/40 px-4 py-3 shrink-0 space-y-3">
                <div className="flex items-start gap-1.5 text-xs">
                  <Sparkles className="w-4 h-4 text-accent shrink-0 mt-0.5" />
                  <div className="min-w-0 flex-1">
                    <span className="text-muted-foreground font-medium">Selected text to add:</span>
                    <p className="font-mono bg-background border border-border rounded-sm p-1.5 mt-1 font-semibold truncate">
                      "{selectedText}"
                    </p>
                  </div>
                </div>

                <div className="grid grid-cols-3 gap-2">
                  <label className="flex items-center gap-1 text-[11px] cursor-pointer font-medium">
                    <input
                      type="radio"
                      name="saveType"
                      checked={saveType === "customRule"}
                      onChange={() => setSaveType("customRule")}
                    />
                    Search Override
                  </label>
                  <label className="flex items-center gap-1 text-[11px] cursor-pointer font-medium">
                    <input
                      type="radio"
                      name="saveType"
                      checked={saveType === "checklist"}
                      onChange={() => setSaveType("checklist")}
                    />
                    Checklist Keyword
                  </label>
                  <label className="flex items-center gap-1 text-[11px] cursor-pointer font-medium">
                    <input
                      type="radio"
                      name="saveType"
                      checked={saveType === "opportunity"}
                      onChange={() => setSaveType("opportunity")}
                    />
                    Opportunity Match
                  </label>
                </div>

                {saveType === "customRule" ? (
                  <div className="space-y-2">
                    <div className="space-y-1">
                      <label className="block text-[10px] text-muted-foreground uppercase font-semibold">
                        Announcement Type
                      </label>
                      <input
                        type="text"
                        value={announcementTypeInput}
                        onChange={(e) => setAnnouncementTypeInput(e.target.value)}
                        className="w-full h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                        placeholder="e.g. Proposed issue of securities"
                      />
                    </div>
                    <div className="space-y-1">
                      <label className="block text-[10px] text-muted-foreground uppercase font-semibold">
                        Action Override
                      </label>
                      <div className="flex gap-4">
                        <label className="flex items-center gap-1.5 text-xs cursor-pointer font-medium text-[#375623]">
                          <input
                            type="radio"
                            name="customAction"
                            checked={customAction === "include"}
                            onChange={() => setCustomAction("include")}
                          />
                          Include (RAG GREEN)
                        </label>
                        <label className="flex items-center gap-1.5 text-xs cursor-pointer font-medium text-[#9C0006]">
                          <input
                            type="radio"
                            name="customAction"
                            checked={customAction === "exclude"}
                            onChange={() => setCustomAction("exclude")}
                          />
                          Exclude (RAG RED)
                        </label>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="space-y-1">
                    <label className="block text-[10px] text-muted-foreground uppercase font-semibold">
                      Target {saveType === "checklist" ? "Checklist Item" : "Opportunity Rule"}
                    </label>
                    <select
                      value={selectedTargetId}
                      onChange={(e) => setSelectedTargetId(e.target.value)}
                      className="w-full h-8 px-2 text-xs border border-input rounded-sm bg-background focus:outline-none focus:ring-1 focus:ring-ring"
                    >
                      {saveType === "checklist"
                        ? checklistItems.map((item) => (
                            <option key={item.id} value={item.id}>
                              {item.standard} &middot; {item.title}
                            </option>
                          ))
                        : OPPORTUNITY_RULES.map((rule) => (
                            <option key={rule.id} value={rule.id}>
                              {rule.label}
                            </option>
                          ))}
                    </select>
                  </div>
                )}

                {saveStatus && (
                  <div
                    className={`text-xs p-2 rounded-sm ${
                      saveStatus.type === "success"
                        ? "bg-[#C6E0B4] text-[#375623]"
                        : "bg-[#FFC7CE] text-[#9C0006]"
                    }`}
                  >
                    {saveStatus.msg}
                  </div>
                )}

                <div className="flex gap-2 justify-end">
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setSelectedText("")}
                    className="text-xs h-8"
                  >
                    Cancel
                  </Button>
                  <Button
                    onClick={handleSaveKeyword}
                    disabled={savingKeyword || (saveType !== "customRule" && !selectedTargetId)}
                    size="sm"
                    className="text-xs h-8 bg-accent hover:bg-accent/90 flex items-center gap-1.5"
                  >
                    {savingKeyword ? (
                      <Loader2 className="w-3.5 h-3.5 animate-spin" />
                    ) : (
                      <Save className="w-3.5 h-3.5" />
                    )}
                    Save to memory
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
