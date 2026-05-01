// src/components/accounts/AccountRowMenu.tsx — dropdown for an AccountRow.
// Extracted so AccountRow can stay focused on layout. Only "Remove" is wired
// today; Edit / Mark Primary / Verify Connection are deliberately hidden
// until the underlying server actions exist.
"use client";

import { useState, useTransition } from "react";
import { useRouter } from "next/navigation";
import { MoreHorizontal, Trash2 } from "lucide-react";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { removeAccountFromCreator } from "@/app/(dashboard)/creators/actions";
import { toast } from "sonner";

export function AccountRowMenu({ profileId, handle }: { profileId: string; handle: string }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [isPending, startTransition] = useTransition();

  const handleRemove = () => {
    if (typeof window !== "undefined") {
      const confirmed = window.confirm(
        `Remove @${handle} from this creator?\n\nThe row stays in the database (history is preserved); it just stops appearing on the creator page.`
      );
      if (!confirmed) return;
    }
    setOpen(false);
    startTransition(async () => {
      const r = await removeAccountFromCreator(profileId);
      if (!r.ok) {
        toast.error("Could not remove account", { description: r.error });
        return;
      }
      toast.success("Account removed");
      router.refresh();
    });
  };

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        className="opacity-0 group-hover:opacity-100 transition-opacity inline-flex items-center justify-center h-8 w-8 rounded-full hover:bg-muted text-muted-foreground hover:text-foreground outline-none data-[state=open]:opacity-100"
        aria-label="Account actions"
      >
        <MoreHorizontal className="h-4 w-4" />
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem
          className="text-red-500 focus:text-red-500"
          disabled={isPending}
          onSelect={(e) => {
            // Prevent menu from auto-closing before our confirm() fires.
            e.preventDefault();
            handleRemove();
          }}
        >
          <Trash2 className="mr-2 h-4 w-4" /> {isPending ? "Removing…" : "Remove"}
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
