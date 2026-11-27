import { useEffect } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { Menu, X } from "lucide-react";
import Sidebar from "../components/Sidebar.jsx";
import { useApp } from "../context/AppContext.jsx";

export default function MainLayout() {
  const { sidebarOpen, setSidebarOpen } = useApp();
  const location = useLocation();

  // Close the mobile drawer on navigation
  useEffect(() => setSidebarOpen(false), [location.pathname, setSidebarOpen]);

  // Close with Escape
  useEffect(() => {
    if (!sidebarOpen) return;
    const onKey = (e) => e.key === "Escape" && setSidebarOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [sidebarOpen, setSidebarOpen]);

  return (
    <div className="flex h-full bg-ink-950">
      {/* Desktop sidebar */}
      <aside className="hidden w-72 flex-none border-r border-ink-700 md:block">
        <Sidebar />
      </aside>

      {/* Mobile drawer */}
      <div
        className={`fixed inset-0 z-40 md:hidden ${sidebarOpen ? "pointer-events-auto" : "pointer-events-none"}`}
        aria-hidden={!sidebarOpen}
      >
        <div
          onClick={() => setSidebarOpen(false)}
          className={`absolute inset-0 bg-black/60 transition-opacity duration-200 ${
            sidebarOpen ? "opacity-100" : "opacity-0"
          }`}
        />
        <aside
          className={`absolute inset-y-0 left-0 w-72 max-w-[85%] border-r border-ink-700 shadow-2xl transition-transform duration-200 ${
            sidebarOpen ? "translate-x-0" : "-translate-x-full"
          }`}
        >
          <button
            onClick={() => setSidebarOpen(false)}
            className="btn-ghost absolute right-2 top-3 z-10 !p-1.5"
            aria-label="Close sidebar"
          >
            <X size={18} />
          </button>
          <Sidebar onNavigate={() => setSidebarOpen(false)} />
        </aside>
      </div>

      {/* Main content */}
      <main className="flex min-w-0 flex-1 flex-col">
        <header className="flex items-center gap-2 border-b border-ink-700 px-3 py-2.5 md:hidden">
          <button onClick={() => setSidebarOpen(true)} className="btn-ghost !p-2" aria-label="Open sidebar">
            <Menu size={20} />
          </button>
          <span className="text-sm font-semibold text-zinc-100">Aria</span>
        </header>
        <div className="min-h-0 flex-1">
          <Outlet />
        </div>
      </main>
    </div>
  );
}
