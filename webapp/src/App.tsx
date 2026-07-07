import { useState, useEffect } from "react"
import { BrowserRouter, Routes, Route, useNavigate, useLocation } from "react-router-dom"
import UploadPage from "@/pages/UploadPage"
import ResultsPage from "@/pages/ResultsPage"
import VotesPage from "@/pages/VotesPage"
import AuditPage from "@/pages/AuditPage"
import UnlistedCompaniesPage from "@/pages/UnlistedCompaniesPage"
import UserIdentityModal from "@/components/app/UserIdentityModal"
import { getCurrentUser, saveCurrentUser } from "@/lib/identity"
import type { CurrentUser } from "@/types"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"

const API_BASE = import.meta.env.VITE_API_URL || ""

function AppNavigation() {
  const location = useLocation()
  const navigate = useNavigate()
  
  if (location.pathname === "/votes" || location.pathname === "/audit") return null
  
  const isUnlisted = location.pathname.startsWith("/unlisted")
  const value = isUnlisted ? "unlisted" : "disclosure"
  
  return (
    <div className="bg-white border-b border-border pt-4">
      <div className="container mx-auto px-4">
        <Tabs value={value} onValueChange={(val) => navigate(val === "unlisted" ? "/unlisted" : "/")}>
          <TabsList className="bg-transparent space-x-6 border-b-0">
            <TabsTrigger value="disclosure" className="text-base pb-3">Disclosure Review</TabsTrigger>
            <TabsTrigger value="unlisted" className="text-base pb-3">Unlisted Companies</TabsTrigger>
          </TabsList>
        </Tabs>
      </div>
    </div>
  )
}

export default function App() {
  const [currentUser, setCurrentUser] = useState<CurrentUser | null>(null)
  const [userLoaded, setUserLoaded] = useState(false)

  useEffect(() => {
    setCurrentUser(getCurrentUser())
    setUserLoaded(true)
  }, [])

  const handleUserSave = (user: CurrentUser) => {
    saveCurrentUser(user)
    setCurrentUser(user)
  }

  return (
    <BrowserRouter>
      {userLoaded && !currentUser && (
        <UserIdentityModal onSave={handleUserSave} apiBase={API_BASE} />
      )}
      <AppNavigation />
      <Routes>
        <Route path="/" element={<UploadPage currentUser={currentUser} />} />
        <Route path="/results" element={<ResultsPage currentUser={currentUser} />} />
        <Route path="/votes" element={<VotesPage />} />
        <Route path="/audit" element={<AuditPage />} />
        <Route path="/unlisted" element={<UnlistedCompaniesPage />} />
      </Routes>
    </BrowserRouter>
  )
}
