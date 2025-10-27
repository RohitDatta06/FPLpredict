import { HashRouter, Routes, Route, NavLink } from 'react-router-dom';
// Explicitly add .tsx extension to imports
import Home from './pages/Home.tsx';
import Predictions from './pages/Predictions.tsx';
import Optimizer from './pages/Optimizer.tsx';
// Import icons if you installed them (optional)
// import { LayoutDashboard, BarChart3, Wrench } from 'lucide-react';

// --- Re-usable Navigation Link Component ---
// Updated styles for horizontal layout
function NavItem({ to, children }: { to: string; children: React.ReactNode }) {
  const baseClasses = "flex items-center px-4 py-2 rounded-md text-sm font-medium text-gray-300 hover:bg-[#101010] hover:text-teal-300 transition-colors";
  const activeClasses = "bg-teal-600 text-white";

  return (
    <NavLink
      to={to}
      className={({ isActive }) => `${baseClasses} ${isActive ? activeClasses : ''}`}
    >
      {/* <IconComponent className="mr-2 h-4 w-4" /> Optional Icon */}
      {children}
    </NavLink>
  );
}

// --- Main App Layout ---
export default function App() {
  return (
    // Use HashRouter for better compatibility in dev/static hosting
    <HashRouter>
      {/* Main container changed to flex-col */}
  <div className="flex flex-col h-screen w-full bg-[#2b2b2b] text-gray-100 antialiased">
        
        {/* --- Top Navigation Bar (Horizontal) --- */}
        {/* Updated nav styles: w-full, thinner padding (p-2), items-center */}
  <nav className="w-full border-b border-[#4a4a4a] bg-[#3a3a3a] p-2">
           <div className="container mx-auto flex justify-between items-center">
             {/* Logo/Title */}
             <div className="flex items-center space-x-2">
                {/* Optional: Add a logo image here */}
                <span className="text-xl font-bold text-teal-400">FPL Predictor</span>
             </div>
             
             {/* Navigation Links */}
             <div className="flex space-x-2">
               <NavItem to="/">
                  {/* <LayoutDashboard size={18} /> */}
                  Dashboard
               </NavItem>
               <NavItem to="/predictions">
                  {/* <BarChart3 size={18} /> */}
                  Player Data
               </NavItem>
               <NavItem to="/optimizer">
                  {/* <Wrench size={18} /> */}
                  Optimizer
               </NavItem>
             </div>
           </div>
        </nav>

        {/* --- Main Content Area --- */}
        {/* Takes remaining height, scrollable */}
        <main className="flex-1 overflow-y-auto p-8 container mx-auto">
          {/* This is where your different pages will render */}
          <Routes>
            <Route path="/" element={<Home />} />
            <Route path="/predictions" element={<Predictions />} />
            <Route path="/optimizer" element={<Optimizer />} />
          </Routes>
        </main>
      </div>
    </HashRouter>
  );
}

