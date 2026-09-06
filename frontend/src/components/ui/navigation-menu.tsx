"use client";

import * as React from "react";
import {
  motion,
  useScroll,
  useMotionValueEvent,
  type Variants,
} from "framer-motion";
import { Menu } from "lucide-react";
import { cn } from "@/lib/utils";

const EXPAND_SCROLL_THRESHOLD = 80;
const COLLAPSE_AFTER = 150;

const containerVariants: Variants = {
  expanded: {
    y: 0,
    opacity: 1,
    width: "auto",
    transition: {
      y: { type: "spring", damping: 18, stiffness: 250 },
      opacity: { duration: 0.3 },
      type: "spring",
      damping: 20,
      stiffness: 300,
      staggerChildren: 0.07,
      delayChildren: 0.2,
    },
  },
  collapsed: {
    y: 0,
    opacity: 1,
    width: "3rem",
    transition: {
      type: "spring",
      damping: 20,
      stiffness: 300,
      when: "afterChildren",
      staggerChildren: 0.05,
      staggerDirection: -1,
    },
  },
};

const logoVariants: Variants = {
  expanded: {
    opacity: 1,
    x: 0,
    transition: { type: "spring", damping: 15 },
  },
  collapsed: { opacity: 0, x: -25, transition: { duration: 0.3 } },
};

const itemVariants: Variants = {
  expanded: {
    opacity: 1,
    x: 0,
    scale: 1,
    transition: { type: "spring", damping: 15 },
  },
  collapsed: { opacity: 0, x: -20, scale: 0.95, transition: { duration: 0.2 } },
};

const collapsedIconVariants: Variants = {
  expanded: { opacity: 0, scale: 0.8, transition: { duration: 0.2 } },
  collapsed: {
    opacity: 1,
    scale: 1,
    transition: { type: "spring", damping: 15, stiffness: 300, delay: 0.15 },
  },
};

export interface AnimatedNavItem {
  name: string;
  /** Called on click. The nav handles collapsing/expanding itself. */
  onSelect: () => void;
}

export interface AnimatedNavProps {
  items: AnimatedNavItem[];
  /** Rendered in the leading slot, e.g. a wordmark. */
  logo?: React.ReactNode;
  /** Rendered after the items, e.g. account controls. */
  trailing?: React.ReactNode;
  className?: string;
}

/**
 * A floating pill nav that collapses to a circle as you scroll down and
 * expands again when you scroll back up. Click the collapsed circle to
 * expand it without scrolling.
 */
export function AnimatedNav({
  items,
  logo,
  trailing,
  className,
}: AnimatedNavProps) {
  const [isExpanded, setExpanded] = React.useState(true);

  const { scrollY } = useScroll();
  const lastScrollY = React.useRef(0);
  // Where the user last reversed into an upward scroll. Anchoring the expand
  // threshold here (rather than at the point where the nav collapsed) is what
  // makes "scroll up a little to get the nav back" work anywhere on a long
  // page, instead of only near the collapse point.
  const upwardScrollAnchor = React.useRef(0);

  useMotionValueEvent(scrollY, "change", (latest) => {
    const previous = lastScrollY.current;
    lastScrollY.current = latest;

    if (isExpanded) {
      if (latest > previous && latest > COLLAPSE_AFTER) {
        setExpanded(false);
        upwardScrollAnchor.current = latest;
      }
      return;
    }

    if (latest >= previous) {
      // Still heading down, so keep moving the turnaround point with them.
      upwardScrollAnchor.current = latest;
      return;
    }

    if (
      upwardScrollAnchor.current - latest > EXPAND_SCROLL_THRESHOLD ||
      latest < COLLAPSE_AFTER
    ) {
      setExpanded(true);
    }
  });

  function handleNavClick(e: React.MouseEvent) {
    if (!isExpanded) {
      e.preventDefault();
      setExpanded(true);
    }
  }

  return (
    <div className="fixed top-5 left-1/2 -translate-x-1/2 z-50">
      <motion.nav
        aria-label="Primary"
        initial={{ y: -80, opacity: 0 }}
        animate={isExpanded ? "expanded" : "collapsed"}
        variants={containerVariants}
        whileHover={!isExpanded ? { scale: 1.1 } : undefined}
        whileTap={!isExpanded ? { scale: 0.95 } : undefined}
        onClick={handleNavClick}
        className={cn(
          "relative flex h-12 items-center overflow-hidden rounded-full border border-border bg-background/85 shadow-lg backdrop-blur-md",
          isExpanded
            ? "gap-5 px-2 sm:gap-0 sm:min-w-[min(44rem,calc(100vw-2.5rem))] sm:justify-between"
            : "cursor-pointer justify-center",
          className,
        )}
      >
        {logo && (
          <motion.div
            variants={logoVariants}
            className="flex shrink-0 items-center pl-3"
          >
            {logo}
          </motion.div>
        )}

        <motion.div
          className={cn(
            "flex items-center gap-1 sm:gap-3",
            !isExpanded && "pointer-events-none",
          )}
        >
          {items.map((item) => (
            <motion.button
              key={item.name}
              type="button"
              variants={itemVariants}
              onClick={(e) => {
                e.stopPropagation();
                item.onSelect();
              }}
              className="rounded-full px-2 py-1 text-sm font-medium text-muted-foreground transition-colors hover:text-foreground"
            >
              {item.name}
            </motion.button>
          ))}
        </motion.div>

        {trailing && (
          <motion.div
            variants={itemVariants}
            onClick={(e) => e.stopPropagation()}
            className={cn(
              "flex shrink-0 items-center gap-1.5 pr-2",
              !isExpanded && "pointer-events-none",
            )}
          >
            {trailing}
          </motion.div>
        )}

        <div className="pointer-events-none absolute inset-0 flex items-center justify-center">
          <motion.div
            variants={collapsedIconVariants}
            animate={isExpanded ? "expanded" : "collapsed"}
          >
            <Menu className="h-5 w-5 text-foreground" />
          </motion.div>
        </div>
      </motion.nav>
    </div>
  );
}
