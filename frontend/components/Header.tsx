"use client";
import { useEffect, useState } from "react";
import Link from "next/link";
import { usePathname } from "next/navigation";

function getTheme(): "dark" | "light" {
  if (typeof window === "undefined") return "dark";
  const s = localStorage.getItem("ci-theme") as "dark" | "light" | null;
  if (s) return s;
  return window.matchMedia("(prefers-color-scheme:light)").matches ? "light" : "dark";
}
function applyTheme(t: "dark" | "light") {
  document.documentElement.setAttribute("data-theme", t);
  localStorage.setItem("ci-theme", t);
}

const SunIcon = () => (
  <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="5"/><line x1="12" y1="1" x2="12" y2="3"/><line x1="12" y1="21" x2="12" y2="23"/>
    <line x1="4.22" y1="4.22" x2="5.64" y2="5.64"/><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"/>
    <line x1="1" y1="12" x2="3" y2="12"/><line x1="21" y1="12" x2="23" y2="12"/>
    <line x1="4.22" y1="19.78" x2="5.64" y2="18.36"/><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"/>
  </svg>
);
const MoonIcon = () => (
  <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"/>
  </svg>
);

const NAV = [
  { href: "/", label: "Dashboard" },
  { href: "/cases/demo_healthy_001", label: "Healthy Case" },
  { href: "/cases/demo_risky_002", label: "Risky Case" },
];

export default function Header() {
  const pathname = usePathname();
  const [theme, setTheme]   = useState<"dark"|"light">("dark");
  const [mounted, setMounted] = useState(false);
  const [scrolled, setScrolled] = useState(false);

  useEffect(() => { const t = getTheme(); setTheme(t); setMounted(true); }, []);
  useEffect(() => {
    const fn = () => setScrolled(window.scrollY > 6);
    window.addEventListener("scroll", fn, { passive: true });
    return () => window.removeEventListener("scroll", fn);
  }, []);

  function toggle() { const n = theme === "dark" ? "light" : "dark"; setTheme(n); applyTheme(n); }

  return (
    <header className={`topbar${scrolled ? " scrolled" : ""}`}>
      <div className="topbar-inner">
        {/* Brand */}
        <Link href="/" style={{ display:"flex", alignItems:"center", gap:12, textDecoration:"none", flexShrink:0 }}>
          <div style={{
            width:38, height:38, borderRadius:10, flexShrink:0,
            background:"linear-gradient(135deg, var(--blue) 0%, var(--purple) 100%)",
            display:"flex", alignItems:"center", justifyContent:"center",
            boxShadow:"0 2px 14px var(--blue-g)",
            transition:"box-shadow .25s, transform .2s",
          }}
          onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.transform="scale(1.06) rotate(4deg)";}}
          onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.transform="";}}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" fill="none">
              <path d="M10 2L18 10L10 18L2 10Z" fill="rgba(255,255,255,0.18)" stroke="rgba(255,255,255,0.55)" strokeWidth="1"/>
              <path d="M10 6L14 10L10 14L6 10Z" fill="white"/>
            </svg>
          </div>
          <div>
            <div style={{
              fontFamily:"var(--font)", fontSize:18, fontWeight:800, letterSpacing:"-0.03em", lineHeight:1,
              background:"linear-gradient(135deg, var(--blue), var(--purple))",
              WebkitBackgroundClip:"text", WebkitTextFillColor:"transparent", backgroundClip:"text",
            }}>Credit Intel</div>
            <div style={{ fontSize:10, fontWeight:600, letterSpacing:"0.12em", textTransform:"uppercase", color:"var(--t3)", lineHeight:1.3 }}>
              AI Appraisal Platform
            </div>
          </div>
        </Link>

        {/* Separator */}
        <div style={{ width:1, height:30, background:"var(--gb)", margin:"0 24px", flexShrink:0 }} />

        {/* Nav */}
        <nav style={{ display:"flex", gap:4 }}>
          {NAV.map(({ href, label }) => {
            const active = pathname === href || (href !== "/" && pathname?.startsWith(href));
            return (
              <Link key={href} href={href} style={{
                padding:"7px 14px", borderRadius:"var(--r-md)",
                fontSize:14, fontWeight:600,
                color: active ? "var(--blue)" : "var(--t2)",
                background: active ? "var(--blue-s)" : "transparent",
                border:`1px solid ${active ? "var(--blue-g)" : "transparent"}`,
                textDecoration:"none",
                transition:"all .18s var(--ease)",
                backdropFilter: active ? "blur(8px)" : "none",
              }}
              onMouseEnter={e=>{ if(!active){const el=e.currentTarget as HTMLElement; el.style.color="var(--t1)"; el.style.background="var(--surf)"; el.style.borderColor="var(--gb)"; }}}
              onMouseLeave={e=>{ if(!active){const el=e.currentTarget as HTMLElement; el.style.color="var(--t2)"; el.style.background="transparent"; el.style.borderColor="transparent"; }}}
              >
                {label}
              </Link>
            );
          })}
        </nav>

        <div style={{ flex:1 }} />

        {/* Right cluster */}
        <div style={{ display:"flex", alignItems:"center", gap:10 }}>
          {/* Live badge */}
          <div style={{
            display:"flex", alignItems:"center", gap:7,
            padding:"5px 13px", borderRadius:"var(--r-pill)",
            background:"var(--green-s)", border:"1px solid var(--green-g)",
            fontSize:11, fontWeight:700, color:"var(--green)",
            textTransform:"uppercase", letterSpacing:"0.07em",
            backdropFilter:"blur(10px)",
          }}>
            <span style={{ width:7, height:7, borderRadius:"50%", background:"var(--green)", display:"inline-block", boxShadow:"0 0 6px var(--green-g)", animation:"blink 2s ease-in-out infinite" }} />
            AI Live
          </div>

          <div style={{ width:1, height:24, background:"var(--gb)" }} />

          {/* Theme toggle */}
          {mounted && (
            <button onClick={toggle} title={theme === "dark" ? "Switch to light" : "Switch to dark"} style={{
              width:38, height:38, borderRadius:"var(--r-md)",
              border:"1px solid var(--gb)", background:"var(--glass-2)",
              color:"var(--t2)", cursor:"pointer", backdropFilter:"blur(12px)",
              display:"flex", alignItems:"center", justifyContent:"center",
              transition:"all .18s var(--ease)",
            }}
            onMouseEnter={e=>{const el=e.currentTarget as HTMLElement; el.style.borderColor="var(--blue)"; el.style.color="var(--blue)"; el.style.background="var(--blue-s)"; el.style.transform="scale(1.05)";}}
            onMouseLeave={e=>{const el=e.currentTarget as HTMLElement; el.style.borderColor="var(--gb)"; el.style.color="var(--t2)"; el.style.background="var(--glass-2)"; el.style.transform="";}}
            >
              {theme === "dark" ? <SunIcon /> : <MoonIcon />}
            </button>
          )}

          {/* Avatar */}
          <div style={{
            width:36, height:36, borderRadius:"50%",
            background:"linear-gradient(135deg, var(--blue), var(--purple))",
            display:"flex", alignItems:"center", justifyContent:"center",
            fontSize:12, fontWeight:800, color:"#fff",
            boxShadow:"0 2px 12px var(--blue-g)",
            userSelect:"none", cursor:"default",
            transition:"transform .2s var(--spring)",
          }}
          onMouseEnter={e=>{(e.currentTarget as HTMLElement).style.transform="scale(1.08)";}}
          onMouseLeave={e=>{(e.currentTarget as HTMLElement).style.transform="";}}
          >CA</div>
        </div>
      </div>
    </header>
  );
}