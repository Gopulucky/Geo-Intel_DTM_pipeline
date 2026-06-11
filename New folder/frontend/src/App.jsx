// frontend/src/App.jsx
import { BrowserRouter, Routes, Route } from "react-router-dom";
import HomePage      from "./pages/HomePage";
import ProcessingPage from "./pages/ProcessingPage";
import ResultsPage   from "./pages/ResultsPage";

export default function App() {
  return (
    <BrowserRouter future={{ v7_startTransition: true, v7_relativeSplatPath: true }}>
      <Routes>
        <Route path="/"                    element={<HomePage />} />
        <Route path="/processing/:jobId"   element={<ProcessingPage />} />
        <Route path="/results/:jobId"      element={<ResultsPage />} />
      </Routes>
    </BrowserRouter>
  );
}
