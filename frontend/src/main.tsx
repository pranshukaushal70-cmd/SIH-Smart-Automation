import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom";
import "./index.css";
import Layout from "./components/Layout";
import { ToastProvider } from "./components/ui";
import Dashboard from "./pages/Dashboard";
import Applications from "./pages/Applications";
import Workspace, { ReviewLanding } from "./pages/Workspace";
import Rules from "./pages/Rules";
import Reports from "./pages/Reports";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <ToastProvider>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route index element={<Dashboard />} />
            <Route path="applications" element={<Applications />} />
            <Route path="applications/:id" element={<Workspace />} />
            <Route path="review" element={<ReviewLanding />} />
            <Route path="rules" element={<Rules />} />
            <Route path="reports" element={<Reports />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </ToastProvider>
  </React.StrictMode>,
);
