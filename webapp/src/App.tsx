import { BrowserRouter, Routes, Route } from "react-router-dom"
import UploadPage from "@/pages/UploadPage"
import ResultsPage from "@/pages/ResultsPage"

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<UploadPage />} />
        <Route path="/results" element={<ResultsPage />} />
      </Routes>
    </BrowserRouter>
  )
}
