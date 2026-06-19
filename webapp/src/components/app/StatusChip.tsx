import { cn } from "@/lib/utils"
import type { RenderStatus } from "@/types"

const STATUS_CLASSES: Record<RenderStatus, string> = {
  "Addressed":               "status-addressed",
  "Represented differently": "status-represented",
  "Not detected":            "status-notfound",
  "Below materiality":       "status-below",
  "N/A":                     "bg-muted text-muted-foreground",
}

interface Props {
  status: RenderStatus
  className?: string
}

export function StatusChip({ status, className }: Props) {
  return (
    <span className={cn("inline-flex items-center rounded-sm px-2 py-0.5 text-xs font-medium", STATUS_CLASSES[status], className)}>
      {status}
    </span>
  )
}
