"use client";
/**
 * AnimateIn — lightweight scroll-reveal wrapper.
 * Wraps children and adds .reveal class + IntersectionObserver.
 * Usage: <AnimateIn delay={0.1}><YourCard /></AnimateIn>
 */
import { useEffect, useRef } from "react";

type Props = {
  children: React.ReactNode;
  delay?: number;   /* seconds */
  className?: string;
  style?: React.CSSProperties;
  as?: keyof JSX.IntrinsicElements;
};

export default function AnimateIn({ children, delay = 0, className = "", style, as: Tag = "div" }: Props) {
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

  return (
    // @ts-expect-error dynamic tag
    <Tag
      ref={ref}
      className={`reveal${className ? " " + className : ""}`}
      style={{ transitionDelay: delay ? `${delay}s` : undefined, ...style }}
    >
      {children}
    </Tag>
  );
}