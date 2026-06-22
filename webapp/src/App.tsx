import { useState, useEffect } from "react"
import { BrowserRouter, Routes, Route } from "react-router-dom"
import UploadPage from "@/pages/UploadPage"
import ResultsPage from "@/pages/ResultsPage"
import VotesPage from "@/pages/VotesPage"
import AuditPage from "@/pages/AuditPage"
import UserIdentityModal from "@/components/app/UserIdentityModal"
import { getCurrentUser, saveCurrentUser } from "@/lib/identity"
import type { CurrentUser } from "@/types"

const API_BASE = import.meta.env.VITE_API_URL || ""

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
      <Routes>
        <Route path="/" element={<UploadPage currentUser={currentUser} />} />
        <Route path="/results" element={<ResultsPage currentUser={currentUser} />} />
        <Route path="/votes" element={<VotesPage />} />
        <Route path="/audit" element={<AuditPage />} />
      </Routes>
    </BrowserRouter>
  )
}
