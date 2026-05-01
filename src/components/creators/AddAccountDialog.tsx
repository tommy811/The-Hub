"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Plus, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { addAccountToCreator } from "@/app/(dashboard)/creators/actions";
import { toast } from "sonner";
import type { Enums } from "@/types/db";

const PLATFORMS = [
  { value: 'instagram',         label: 'Instagram',         group: 'Social' },
  { value: 'tiktok',            label: 'TikTok',            group: 'Social' },
  { value: 'youtube',           label: 'YouTube',           group: 'Social' },
  { value: 'twitter',           label: 'Twitter / X',       group: 'Social' },
  { value: 'facebook',          label: 'Facebook',          group: 'Social' },
  { value: 'linkedin',          label: 'LinkedIn',          group: 'Social' },
  { value: 'onlyfans',          label: 'OnlyFans',          group: 'Monetization' },
  { value: 'fanvue',            label: 'Fanvue',            group: 'Monetization' },
  { value: 'fanplace',          label: 'Fanplace',          group: 'Monetization' },
  { value: 'patreon',           label: 'Patreon',           group: 'Monetization' },
  { value: 'amazon_storefront', label: 'Amazon Storefront', group: 'Monetization' },
  { value: 'tiktok_shop',       label: 'TikTok Shop',       group: 'Monetization' },
  { value: 'linktree',          label: 'Linktree',          group: 'Link-in-Bio' },
  { value: 'beacons',           label: 'Beacons',           group: 'Link-in-Bio' },
  { value: 'custom_domain',     label: 'Custom Domain',     group: 'Link-in-Bio' },
  { value: 'telegram_channel',  label: 'Telegram Channel',  group: 'Messaging' },
  { value: 'telegram_cupidbot', label: 'Telegram CupidBot', group: 'Messaging' },
  { value: 'other',             label: 'Other',             group: 'Other' },
];

const PLATFORM_TO_ACCOUNT_TYPE: Record<string, string> = {
  instagram: 'social', tiktok: 'social', youtube: 'social', twitter: 'social', facebook: 'social', linkedin: 'social',
  onlyfans: 'monetization', fanvue: 'monetization', fanplace: 'monetization', patreon: 'monetization',
  amazon_storefront: 'monetization', tiktok_shop: 'monetization',
  linktree: 'link_in_bio', beacons: 'link_in_bio', custom_domain: 'link_in_bio',
  telegram_channel: 'messaging', telegram_cupidbot: 'messaging',
  other: 'other',
};

const ACCOUNT_TYPES = [
  { value: 'social',       label: 'Social' },
  { value: 'monetization', label: 'Monetization' },
  { value: 'link_in_bio',  label: 'Link-in-Bio' },
  { value: 'messaging',    label: 'Messaging' },
  { value: 'other',        label: 'Other' },
];

export function AddAccountDialog({
  creatorId,
  defaultAccountType = 'social',
  trigger,
}: {
  creatorId: string;
  defaultAccountType?: string;
  /**
   * Optional custom trigger element. If omitted, the dialog renders its
   * built-in compact "Add manually" link (used by per-section UIs).
   * Pass a Button for the page-header variant.
   */
  trigger?: React.ReactNode;
}) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Pick a sensible default platform for the chosen account type so the
  // form opens pre-filled with a coherent platform/type pair.
  const defaultPlatform = (() => {
    switch (defaultAccountType) {
      case 'monetization': return 'onlyfans';
      case 'link_in_bio': return 'linktree';
      case 'messaging': return 'telegram_channel';
      case 'other': return 'other';
      default: return 'instagram';
    }
  })();

  const [platform, setPlatform] = useState(defaultPlatform);
  const [accountType, setAccountType] = useState(defaultAccountType);
  const [handle, setHandle] = useState('');
  const [url, setUrl] = useState('');
  const [displayName, setDisplayName] = useState('');
  const [runDiscovery, setRunDiscovery] = useState<boolean>(true);

  const handlePlatformChange = (val: string | null) => {
    if (!val) return;
    setPlatform(val);
    setAccountType(PLATFORM_TO_ACCOUNT_TYPE[val] ?? 'other');
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!handle.trim()) return;
    setLoading(true);
    setError(null);
    const result = await addAccountToCreator(creatorId, {
      platform: platform as Enums<"platform">,
      handle: handle.trim(),
      accountType: accountType as Enums<"account_type">,
      url: url.trim() || undefined,
      displayName: displayName.trim() || undefined,
      runDiscovery,
    });
    setLoading(false);
    if (!result.ok) {
      setError(result.error);
      toast.error("Could not add account", { description: result.error });
      return;
    }
    toast.success(runDiscovery ? "Account added — discovery queued" : "Account added");
    setOpen(false);
    setHandle('');
    setUrl('');
    setDisplayName('');
    setPlatform(defaultPlatform);
    setAccountType(defaultAccountType);
    setRunDiscovery(true);
    router.refresh();
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      {trigger ? (
        // base-ui's Trigger forwards refs/handlers via the `render` prop
        // (no `asChild`). React.isValidElement narrows the type so the cast
        // is safe.
        <DialogTrigger render={trigger as React.ReactElement} />
      ) : (
        <DialogTrigger className="inline-flex items-center gap-1 text-xs font-medium text-indigo-400 hover:text-indigo-300 transition-colors px-2 py-1 rounded hover:bg-muted/40">
          <Plus className="h-3.5 w-3.5" /> Add manually
        </DialogTrigger>
      )}
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add Account Manually</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="flex flex-col gap-4 mt-2">
          <div className="grid grid-cols-2 gap-3">
            <div className="flex flex-col gap-1.5">
              <Label>Platform</Label>
              <Select value={platform} onValueChange={handlePlatformChange}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {['Social', 'Monetization', 'Link-in-Bio', 'Messaging', 'Other'].map(group => (
                    <div key={group}>
                      <div className="px-2 py-1.5 text-[10px] font-bold uppercase tracking-widest text-muted-foreground">{group}</div>
                      {PLATFORMS.filter(p => p.group === group).map(p => (
                        <SelectItem key={p.value} value={p.value}>{p.label}</SelectItem>
                      ))}
                    </div>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="flex flex-col gap-1.5">
              <Label>Account Type</Label>
              <Select value={accountType} onValueChange={(v) => v && setAccountType(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ACCOUNT_TYPES.map(t => (
                    <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Handle <span className="text-red-500">*</span></Label>
            <Input
              placeholder="e.g. sunnyrose"
              value={handle}
              onChange={e => setHandle(e.target.value)}
              required
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>URL <span className="text-muted-foreground text-xs">(optional)</span></Label>
            <Input
              placeholder="https://..."
              value={url}
              onChange={e => setUrl(e.target.value)}
              type="url"
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label>Display Name <span className="text-muted-foreground text-xs">(optional)</span></Label>
            <Input
              placeholder="e.g. Sunny Rose"
              value={displayName}
              onChange={e => setDisplayName(e.target.value)}
            />
          </div>

          <div className="flex items-center gap-2 pt-2">
            <input
              id="run-discovery"
              type="checkbox"
              checked={runDiscovery}
              onChange={(e) => setRunDiscovery(e.target.checked)}
              className="h-4 w-4 rounded border-neutral-700 bg-neutral-900 text-indigo-500 focus:ring-2 focus:ring-indigo-500 focus:ring-offset-0 cursor-pointer"
            />
            <label htmlFor="run-discovery" className="text-sm text-neutral-300 cursor-pointer">
              Run discovery on this account (find network + monetization)
            </label>
          </div>

          {error && <p className="text-xs text-red-500">{error}</p>}

          <div className="flex justify-end gap-2 mt-1">
            <Button type="button" variant="ghost" onClick={() => setOpen(false)} disabled={loading}>Cancel</Button>
            <Button type="submit" disabled={loading || !handle.trim()}>
              {loading ? <><Loader2 className="h-4 w-4 mr-2 animate-spin" /> Adding…</> : 'Add Account'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
