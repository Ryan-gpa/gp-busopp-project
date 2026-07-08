import { useState, useEffect } from "react"
import { AlertCircle, CheckCircle2, Clock } from "lucide-react"

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

function StatusIndicator({ state }: { state: "green" | "amber" | "red" }) {
  if (state === "green") return <CheckCircle2 className="w-6 h-6 text-emerald-500" />
  if (state === "amber") return <Clock className="w-6 h-6 text-amber-500" />
  return <AlertCircle className="w-6 h-6 text-rose-500" />
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

  if (!data && !error) {
    return (
      <div className="container mx-auto py-12 px-4 max-w-4xl text-center">
        <p className="text-gray-500">Loading system status...</p>
      </div>
    )
  }

  const udb = data?.unified_db
  const asic = data?.asic_register
  const inf = data?.infringements
  const apollo = data?.apollo
  const rr = data?.rocketreach

  const udbState = udb?.building ? "amber" : (udb?.exists ? "green" : "red")
  const asicState = asic?.building ? "amber" : (asic?.exists ? "green" : "red")
  const infState = inf?.exists ? "green" : "amber"
  const apolloState = !apollo?.configured ? "red" : (apollo.rate_limited || apollo.credits_exhausted ? "amber" : "green")
  const rrState = rr?.configured ? "green" : "amber"

  return (
    <div className="container mx-auto py-12 px-4 max-w-4xl">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-gray-900 tracking-tight">System Status</h1>
        <p className="text-gray-500 mt-2">Real-time health of integrated databases and APIs.</p>
        
        {error && (
          <div className="mt-4 p-4 bg-rose-50 text-rose-700 rounded-lg flex items-center gap-2">
            <AlertCircle className="w-5 h-5" />
            <span>Could not reach backend: {error}</span>
          </div>
        )}
      </div>

      <div className="grid md:grid-cols-2 gap-6">
        {/* Unified DB */}
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-lg text-gray-900">Unified Companies DB</h3>
              <p className="text-sm text-gray-500">The core local SQLite search index</p>
            </div>
            <StatusIndicator state={udbState} />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <span className="font-medium text-gray-900">
                {udb?.building ? "Building in background..." : (udb?.exists ? "Ready" : "Missing")}
              </span>
            </div>
            {udb?.exists && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-500">File Size</span>
                  <span className="font-medium text-gray-900">{udb.size_mb} MB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Last Modified</span>
                  <span className="font-medium text-gray-900">
                    {udb.last_modified ? new Date(udb.last_modified * 1000).toLocaleString() : "Unknown"}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* Apollo */}
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-lg text-gray-900">Apollo API</h3>
              <p className="text-sm text-gray-500">Primary data enrichment</p>
            </div>
            <StatusIndicator state={apolloState} />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Configured</span>
              <span className="font-medium text-gray-900">{apollo?.configured ? "Yes" : "No"}</span>
            </div>
            {apollo?.configured && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-500">Rate Limited</span>
                  <span className={`font-medium ${apollo.rate_limited ? "text-amber-600" : "text-emerald-600"}`}>
                    {apollo.rate_limited ? "Yes (Paused)" : "No"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Hourly Quota</span>
                  <span className="font-medium text-gray-900">
                    {apollo.hourly_left ?? "?"} / {apollo.hourly_limit ?? "?"}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* ASIC Register */}
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-lg text-gray-900">Raw ASIC Register</h3>
              <p className="text-sm text-gray-500">data.gov.au snapshot</p>
            </div>
            <StatusIndicator state={asicState} />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <span className="font-medium text-gray-900">
                {asic?.building ? "Downloading CSV..." : (asic?.exists ? "Ready" : "Missing")}
              </span>
            </div>
            {asic?.exists && (
              <div className="flex justify-between">
                <span className="text-gray-500">File Size</span>
                <span className="font-medium text-gray-900">{asic.size_mb} MB</span>
              </div>
            )}
          </div>
        </div>

        {/* Infringements */}
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-lg text-gray-900">ASIC Infringements</h3>
              <p className="text-sm text-gray-500">Notices dataset</p>
            </div>
            <StatusIndicator state={infState} />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Status</span>
              <span className="font-medium text-gray-900">
                {inf?.exists ? "Ready" : "Missing"}
              </span>
            </div>
            {inf?.exists && (
              <>
                <div className="flex justify-between">
                  <span className="text-gray-500">File Size</span>
                  <span className="font-medium text-gray-900">{inf.size_kb} KB</span>
                </div>
                <div className="flex justify-between">
                  <span className="text-gray-500">Last Modified</span>
                  <span className="font-medium text-gray-900">
                    {inf.last_modified ? new Date(inf.last_modified * 1000).toLocaleString() : "Unknown"}
                  </span>
                </div>
              </>
            )}
          </div>
        </div>

        {/* RocketReach */}
        <div className="bg-white border rounded-xl p-6 shadow-sm">
          <div className="flex justify-between items-start mb-4">
            <div>
              <h3 className="font-semibold text-lg text-gray-900">RocketReach API</h3>
              <p className="text-sm text-gray-500">Fallback contact enrichment</p>
            </div>
            <StatusIndicator state={rrState} />
          </div>
          <div className="space-y-2 text-sm">
            <div className="flex justify-between">
              <span className="text-gray-500">Configured</span>
              <span className="font-medium text-gray-900">{rr?.configured ? "Yes" : "No"}</span>
            </div>
            {!rr?.configured && (
              <p className="text-xs text-amber-600 mt-2">
                Fallback is disabled. Add ROCKETREACH_API_KEY to environment to enable.
              </p>
            )}
          </div>
        </div>
        
      </div>
    </div>
  )
}
