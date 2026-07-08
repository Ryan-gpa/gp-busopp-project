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

  if (error) {
    return <div className="text-red-600 text-sm mb-4">Backend Status: 🔴 {error}</div>
  }

  if (!data) {
    return <div className="text-gray-500 text-sm mb-4">Loading system status...</div>
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

  return (
    <div className="flex flex-wrap items-center gap-6 text-sm font-medium mb-6 bg-gray-50 p-3 rounded-lg border">
      <div>Unified DB {udbEmoji}</div>
      <div>Raw ASIC {asicEmoji}</div>
      <div>Infringements {infEmoji}</div>
      <div className="flex items-center gap-2">
        Apollo API {apolloEmoji}
        {apollo?.configured && apollo.hourly_left != null && (
          <span className="text-xs text-gray-500 font-normal">
            ({apollo.hourly_left}/{apollo.hourly_limit} calls left)
          </span>
        )}
      </div>
      <div>RocketReach {rrEmoji}</div>
    </div>
  )
}
