"use client";

import * as React from "react";
import { motion, type Variants } from "framer-motion";
import type { LucideIcon } from "lucide-react";
import { cn } from "@/lib/utils";

export interface InviteFeature {
  icon: LucideIcon;
  title: string;
  description: string;
}

export interface InviteCardProps {
  title: string;
  features: InviteFeature[];
  /** Small print above the actions. */
  footnote?: React.ReactNode;
  primaryLabel: string;
  onPrimary: () => void;
  secondaryLabel?: string;
  onSecondary?: () => void;
  className?: string;
}

const card: Variants = {
  hidden: { opacity: 0, y: 12, scale: 0.98 },
  show: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { duration: 0.35, ease: "easeOut", staggerChildren: 0.06 },
  },
};

const row: Variants = {
  hidden: { opacity: 0, y: 8 },
  show: { opacity: 1, y: 0 },
};

/**
 * A centred invitation card: title, a short feature list, fine print, and a
 * primary action with an optional dismissal. Light theme, matching the rest
 * of Sada's palette.
 */
export function InviteCard({
  title,
  features,
  footnote,
  primaryLabel,
  onPrimary,
  secondaryLabel,
  onSecondary,
  className,
}: InviteCardProps) {
  return (
    <motion.div
      variants={card}
      initial="hidden"
      animate="show"
      className={cn(
        "w-full max-w-[380px] rounded-[28px] border border-border bg-background p-6 shadow-xl ring-1 ring-foreground/5",
        className,
      )}
    >
      <motion.h2
        variants={row}
        className="text-center text-[1.6rem] font-semibold leading-tight tracking-tight text-foreground"
      >
        {title}
      </motion.h2>

      <div className="my-5 border-t border-border" />

      <div className="grid gap-4">
        {features.map((f) => (
          <motion.div key={f.title} variants={row} className="flex gap-3.5">
            <span className="flex h-11 w-11 shrink-0 items-center justify-center rounded-2xl bg-primary text-primary-foreground">
              <f.icon className="h-5 w-5" />
            </span>
            <span className="min-w-0">
              <span className="block text-[0.95rem] font-semibold text-foreground">
                {f.title}
              </span>
              <span className="mt-0.5 block text-sm leading-snug text-muted-foreground">
                {f.description}
              </span>
            </span>
          </motion.div>
        ))}
      </div>

      {footnote && (
        <>
          <div className="my-5 border-t border-border" />
          <motion.p
            variants={row}
            className="text-center text-[0.8rem] leading-relaxed text-muted-foreground"
          >
            {footnote}
          </motion.p>
        </>
      )}

      <motion.button
        variants={row}
        type="button"
        onClick={onPrimary}
        className="mt-5 h-12 w-full rounded-full bg-primary text-[0.95rem] font-semibold text-primary-foreground transition-colors hover:bg-primary/90 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 focus-visible:ring-offset-background"
      >
        {primaryLabel}
      </motion.button>

      {secondaryLabel && onSecondary && (
        <motion.button
          variants={row}
          type="button"
          onClick={onSecondary}
          className="mt-1 h-11 w-full rounded-full text-[0.95rem] font-semibold text-foreground transition-colors hover:bg-muted"
        >
          {secondaryLabel}
        </motion.button>
      )}
    </motion.div>
  );
}
