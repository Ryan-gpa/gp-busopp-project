import { useState, useEffect } from "react"

const API_BASE = import.meta.env.VITE_API_URL || ""

type StatusData = {
  unified_db?: { exists: boolean; building: boolean; last_modified: number | null; size_mb: number }
  asic_register?: { exists: boolean; building: boolean; last_modified: number | null; size_mb: number }
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
}

export default function StatusPage() {
  const [data, setData] = useState<StatusData | null>(null)
  const [error, setError] = useState<string | null>(null)

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
  const isLoading = !data && !error;

  if (isLoading) {
    return (
      <div className="flex flex-col items-center justify-center py-6 bg-gray-50 rounded-lg border">
        <div className="w-8 h-8 border-4 border-emerald-500 border-t-transparent rounded-full animate-spin mb-4"></div>
        <div className="text-gray-700 font-medium">Connecting to backend and checking systems...</div>
      </div>
    )
  }

  const udb = data?.unified_db
  const asic = data?.asic_register
  const inf = data?.infringements
  const apollo = data?.apollo
  const rr = data?.rocketreach

  const udbEmoji = udb?.building ? "🟡" : (udb?.exists ? "🟢" : "🔴")
  const asicEmoji = asic?.building ? "🟡" : (asic?.exists ? "🟢" : "🔴")
  const infEmoji = inf?.exists ? "🟢" : "🟡"
  const apolloEmoji = !apollo?.configured ? "🔴" : (apollo.rate_limited || apollo.credits_exhausted ? "🟡" : "🟢")
  const rrEmoji = rr?.configured ? "🟢" : "🟡"

  let pulseMessage = "All systems operational. Ready to search."
  let pulseColor = "text-emerald-700"

  if (error) {
    pulseMessage = `Backend is unreachable (${error}). Please check if the Railway server is running or deploying.`
    pulseColor = "text-red-700 font-bold"
  } else if (udb?.building || asic?.building) {
    pulseMessage = "Database is building in the background. Please wait ~2 minutes. (This page will automatically update when finished)"
    pulseColor = "text-amber-700 font-bold"
  } else if (!udb?.exists || !asic?.exists) {
    pulseMessage = "Core databases are missing. Try restarting the server to trigger a background build."
    pulseColor = "text-red-700 font-bold"
  } else if (!apollo?.configured) {
    pulseMessage = "Apollo API is not configured. Searches will fail. Add APOLLO_API_KEY to your environment."
    pulseColor = "text-red-700 font-bold"
  } else if (apollo?.credits_exhausted) {
    pulseMessage = "Apollo LEAD CREDITS are exhausted. You can still search the local ASIC database, but fetching new CEO/CFO contacts will fail until you upgrade your plan."
    pulseColor = "text-amber-600 font-bold"
  } else if (apollo?.rate_limited) {
    pulseMessage = "Apollo hourly API rate limit reached. Searches will serve from local cache until the hour resets."
    pulseColor = "text-amber-700 font-bold"
  } else if (!rr?.configured) {
    pulseMessage = "All primary systems operational. (Note: RocketReach fallback is disabled)."
    pulseColor = "text-emerald-700"
  }

  return (
    <div className="flex flex-col gap-2 mb-6 bg-gray-50 p-4 rounded-lg border">
      <div className="flex flex-wrap items-center gap-6 text-sm font-medium">
        <div>Unified DB {udbEmoji}</div>
        <div>Raw ASIC {asicEmoji}</div>
        <div>Infringements {infEmoji}</div>
        <div className="flex items-center gap-2">
          Apollo API {apolloEmoji}
          {apollo?.configured && apollo.hourly_left != null && (
            <span className="text-xs text-gray-500 font-normal">
              ({apollo.hourly_left}/{apollo.hourly_limit} API requests/hr)
            </span>
          )}
        </div>
        <div>RocketReach {rrEmoji}</div>
        {error && (
          <div className="text-red-600 ml-auto flex items-center gap-2">
            Backend Error 🔴
            <div className="w-3 h-3 border-2 border-red-600 border-t-transparent rounded-full animate-spin" title="Retrying..."></div>
          </div>
        )}
      </div>
      <div className={`text-sm mt-1 flex items-center gap-2 ${pulseColor}`}>
        <div><span className="font-semibold mr-1">Pulse Check:</span> {pulseMessage}</div>
        {(udb?.building || asic?.building) && (
          <div className="w-3 h-3 border-2 border-amber-500 border-t-transparent rounded-full animate-spin" title="Building..."></div>
        )}
      </div>
    </div>
  )
}
