// src/components/creators/MergeAlertBanner.tsx — Dismissible alert for pending merges
"use client";

import { AlertTriangle, ArrowRight, X } from "lucide-react";
import { AnimatePresence, motion } from "framer-motion";

interface MergeAlertBannerProps {
  count: number;
  onReview: () => void;
  onDismiss?: () => void;
}

export function MergeAlertBanner({ count, onReview, onDismiss }: MergeAlertBannerProps) {
  return (
    <AnimatePresence>
      {count > 0 && (
        <motion.div
          initial={{ opacity: 0, height: 0, marginBottom: 0 }}
          animate={{ opacity: 1, height: "auto", marginBottom: 24 }}
          exit={{ opacity: 0, height: 0, marginBottom: 0 }}
          className="overflow-hidden"
        >
          <div className="flex items-center justify-between p-3 px-4 rounded-xl border border-amber-500/30 bg-amber-500/10 text-amber-500">
            <div className="flex items-center gap-3">
              <AlertTriangle className="h-5 w-5 shrink-0" />
              <span className="text-sm font-medium">
                {count} possible duplicate creator{count > 1 ? 's' : ''} detected during onboarding.
              </span>
            </div>
            <div className="flex items-center gap-2">
              <button 
                onClick={onReview}
                className="flex items-center gap-1 text-sm font-semibold hover:text-amber-400 transition-colors"
              >
                Review <ArrowRight className="h-4 w-4" />
              </button>
              {onDismiss && (
                <button onClick={onDismiss} className="p-1 hover:bg-amber-500/20 rounded opacity-60 hover:opacity-100 transition-all">
                  <X className="h-4 w-4" />
                </button>
              )}
            </div>
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
