import { useState, useEffect } from "react"

const API_BASE = import.meta.env.VITE_API_URL || ""

type StatusData = {
  unified_db?: { exists: boolean; building: boolean; last_modified: number | null; size_mb: number }
  infringements?: { exists: boolean; last_modified: number | null; size_kb: number }
  apollo?: {
    configured: boolean
    rate_limited: boolean
    credits_exhausted: boolean
    hourly_left?: number
    hourly_limit?: number
    last_checked?: number | null
  }
  rocketreach?: { configured: boolean }
  disk?: { total_gb: number; used_gb: number; free_gb: number; used_pct: number }
  volume_files?: { name: string; size_mb: number }[]
}

export default function StatusPage() {
  const [data, setData] = useState<StatusData | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [showDisk, setShowDisk] = useState(false)

  useEffect(() => {
    const fetchStatus = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/admin/system-status`)
        if (!res.ok) throw new Error("Failed to fetch status")
        setData(await res.json())
        setError(null)
      } catch (err: any) {
        setError(err.message)
      }
    }
    fetchStatus()
    const interval = setInterval(fetchStatus, 5000)
    return () => clearInterval(interval)
  }, [])

  const isLoading = !data && !error

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-6 bg-gray-50 rounded-lg border">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4"></div>
        <div className="text-gray-700 font-medium">Connecting to backend...</div>
      </div>
    )
  }

  const udb = data?.unified_db
  const inf = data?.infringements
  const apollo = data?.apollo
  const rr = data?.rocketreach
  const disk = data?.disk
  const files = data?.volume_files ?? []

  const diskPct = disk?.used_pct ?? 0
  const diskEmoji = diskPct > 90 ? "🔴" : diskPct > 75 ? "🟡" : "🟢"

  const udbEmoji = udb?.building ? "🟡" : (udb?.exists ? "🟢" : "🔴")
  const infEmoji = inf?.exists ? "🟢" : "🟡"
  const apolloEmoji = !apollo?.configured ? "🔴" : apollo.credits_exhausted ? "🟡" : apollo.rate_limited ? "🟡" : "🟢"
  const rrEmoji = rr?.configured ? "🟢" : "🟡"

  // --- Pulse Check logic (priority order) ---
  let pulseMessage = ""
  let pulseColor = "text-emerald-700"
  let isBuilding = false

  if (error) {
    pulseMessage = `Backend unreachable (${error}). Railway may still be deploying — check back in 1-2 minutes.`
    pulseColor = "text-red-700 font-bold"
  } else if (udb?.building) {
    pulseMessage = "ASIC database is building in the background (~2-3 min). Page auto-updates when ready — do not refresh."
    pulseColor = "text-amber-700 font-bold"
    isBuilding = true
  } else if (!udb?.exists) {
    pulseMessage = "ASIC database missing. The server will rebuild it automatically on startup. Wait 2-3 minutes then refresh."
    pulseColor = "text-red-700 font-bold"
  } else if (diskPct > 90) {
    pulseMessage = `Disk critically full (${diskPct}% used — ${disk?.free_gb}GB free). Searches may fail. Go to Admin → Purge Old DBs.`
    pulseColor = "text-red-700 font-bold"
  } else if (!apollo?.configured) {
    pulseMessage = "ASIC search works. Apollo contacts disabled — add APOLLO_API_KEY to Railway env vars to enable CEO/CFO lookup."
    pulseColor = "text-amber-600"
  } else if (apollo?.credits_exhausted) {
    pulseMessage = `ASIC search works ✓  |  Apollo lead credits exhausted — 'Find Contacts' will fail until you top up. (${apollo.hourly_left}/${apollo.hourly_limit} API calls/hr remaining)`
    pulseColor = "text-amber-600 font-bold"
  } else if (apollo?.rate_limited) {
    pulseMessage = "Apollo hourly rate limit hit. Searches serve from local cache until the hour resets."
    pulseColor = "text-amber-700 font-bold"
  } else if (!rr?.configured) {
    pulseMessage = `All systems operational — ${udb?.size_mb}MB ASIC DB ready (${(udb?.size_mb ?? 0) > 100 ? "4.4M" : "partial"} records). RocketReach fallback not configured.`
    pulseColor = "text-emerald-700"
  } else {
    pulseMessage = `All systems operational — ${udb?.size_mb}MB ASIC DB ready. Search all 4.4M Australian companies.`
    pulseColor = "text-emerald-700"
  }

  return (
    <div className="flex flex-col gap-2 bg-gray-50 p-4 rounded-lg border text-sm">
      {/* Status indicators row */}
      <div className="flex flex-wrap items-center gap-x-6 gap-y-1 font-medium">
        <div
          className="cursor-pointer hover:underline"
          title={udb ? `${udb.size_mb}MB · Last built: ${udb.last_modified ? new Date(udb.last_modified * 1000).toLocaleString() : "never"}` : "Not found"}
          onClick={() => setShowDisk(v => !v)}
        >
          ASIC DB {udbEmoji}
          {udb?.exists && <span className="font-normal text-gray-500 ml-1">({udb.size_mb}MB)</span>}
        </div>
        <div title={inf?.exists ? `${inf.size_kb}KB infringement notices loaded` : "Not loaded"}>
          Infringements {infEmoji}
        </div>
        <div
          className="flex items-center gap-1.5"
          title={apollo?.configured
            ? `API rate: ${apollo.hourly_left ?? "?"}/${apollo.hourly_limit ?? "?"} calls/hr remaining\nLead credits: ${apollo.credits_exhausted ? "EXHAUSTED" : "available"}`
            : "No API key configured"}
        >
          <span>Apollo {apolloEmoji}</span>
          {apollo?.configured && (
            <span className="text-xs font-normal text-gray-500">
              ({apollo.hourly_left}/{apollo.hourly_limit}/hr
              {apollo.credits_exhausted && <span className="text-amber-600 font-medium ml-1">· credits exhausted</span>})
            </span>
          )}
        </div>
        <div title={rr?.configured ? "RocketReach configured" : "Not configured — add ROCKETREACH_API_KEY"}>
          RocketReach {rrEmoji}
        </div>
        {disk && (
          <div
            className="cursor-pointer hover:underline"
            title={`${disk.used_gb}GB used of ${disk.total_gb}GB total`}
            onClick={() => setShowDisk(v => !v)}
          >
            Disk {diskEmoji} <span className="font-normal text-gray-500">({diskPct}%)</span>
          </div>
        )}
        {error && (
          <div className="text-red-600 ml-auto flex items-center gap-2">
            Backend Error 🔴
            <div className="w-3 h-3 border-2 border-red-600 border-t-transparent rounded-full animate-spin" title="Retrying..." />
          </div>
        )}
      </div>

      {/* Pulse check */}
      <div className={`flex items-center gap-2 mt-0.5 ${pulseColor}`}>
        <span className="font-semibold">Pulse Check:</span>
        <span>{pulseMessage}</span>
        {isBuilding && (
          <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin flex-shrink-0" title="Building..." />
        )}
      </div>

      {/* Expandable disk breakdown */}
      {showDisk && disk && files.length > 0 && (
        <div className="mt-2 pt-2 border-t text-xs text-gray-600 space-y-1">
          <div className="font-semibold text-gray-700 mb-1">Volume Files</div>
          {files.map(f => (
            <div key={f.name} className="flex justify-between">
              <span className="font-mono">{f.name}</span>
              <span>{f.size_mb}MB</span>
            </div>
          ))}
          <div className="flex justify-between font-semibold text-gray-700 border-t pt-1 mt-1">
            <span>Total used</span>
            <span>{disk.used_gb}GB / {disk.total_gb}GB ({diskPct}%)</span>
          </div>
        </div>
      )}
    </div>
  )
}
