"use client";
/**
 * AnimateIn — lightweight scroll-reveal wrapper.
 * Wraps children and adds .reveal class + IntersectionObserver.
 * Usage: <AnimateIn delay={0.1}><YourCard /></AnimateIn>
 * <AnimateIn stagger={1}><YourCard /></AnimateIn>
 */
import React, { useEffect, useRef } from "react";

type Props = {
  children: React.ReactNode;
  delay?: number;   /* specific delay in seconds */
  stagger?: number; /* index for calculating cascaded delays */
  className?: string;
  style?: React.CSSProperties;
  as?: React.ElementType; 
};

export default function AnimateIn({ children, delay, stagger, className = "", style, as: Tag = "div" }: Props) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new IntersectionObserver(
      ([entry]) => { if (entry.isIntersecting) { el.classList.add("visible"); obs.disconnect(); } },
      { threshold: 0.08, rootMargin: "0px 0px -40px 0px" }
    );
    obs.observe(el);
    return () => obs.disconnect();
  }, []);

  // Use explicit delay if provided, otherwise calculate based on stagger index
  const calculatedDelay = delay !== undefined ? `${delay}s` : stagger !== undefined ? `${stagger * 0.1}s` : undefined;

  const combinedStyle: React.CSSProperties = {
    ...style,
    transitionDelay: calculatedDelay,
    // Also inject --stagger as a CSS var just in case child elements want to use it
    ...(stagger !== undefined ? { "--stagger": stagger } as React.CSSProperties : {}),
  };

  return (
    <Tag
      ref={ref}
      className={`reveal${className ? " " + className : ""}`}
      style={combinedStyle}
    >
      {children}
    </Tag>
  );
}