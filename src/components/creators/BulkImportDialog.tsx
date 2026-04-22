// src/components/creators/BulkImportDialog.tsx — Dialog for bulk onboarding creators
"use client";

import { useState, useMemo } from "react";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Plus, Loader2 } from "lucide-react";
import { parseHandles, type ParsedHandle } from "@/lib/handleParser";
import { HandleChipPreview } from "./HandleChipPreview";
import { PLATFORMS } from "@/lib/platforms";

import { bulkImportCreators } from "@/app/actions";

export function BulkImportDialog() {
  const [open, setOpen] = useState(false);
  const [rawText, setRawText] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [trackingType, setTrackingType] = useState("unreviewed");
  const [tags, setTags] = useState("");
  
  // Single handle state
  const [singlePlatform, setSinglePlatform] = useState("");
  const [singleHandle, setSingleHandle] = useState("");
  const [singleUrl, setSingleUrl] = useState("");

  const parsedHandles = useMemo(() => {
    // Pass empty set for now, in a real app we'd fetch existing handles
    return parseHandles(rawText);
  }, [rawText]);

  // Hacky quick state to manage user-assigned platforms for lines that needed it
  const [assignedPlatforms, setAssignedPlatforms] = useState<Record<string, string>>({});

  const finalHandles = parsedHandles.map((ph, idx) => {
    const assigned = assignedPlatforms[`${idx}`];
    if (assigned) {
      return { ...ph, platform: assigned, needsPlatformHint: false };
    }
    return ph;
  });

  const validCount = finalHandles.filter(h => !h.isDuplicate && !h.needsPlatformHint).length;
  const needsHintCount = finalHandles.filter(h => !h.isDuplicate && h.needsPlatformHint).length;
  const duplicateCount = finalHandles.filter(h => h.isDuplicate).length;

  const canSubmitBulk = validCount > 0 && needsHintCount === 0 && !isSubmitting;

  const handleBulkSubmit = async () => {
    setIsSubmitting(true);
    try {
      await bulkImportCreators(rawText, trackingType, tags, assignedPlatforms);
    } catch (e) {
      console.error(e);
    }
    setIsSubmitting(false);
    setOpen(false);
    setRawText("");
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger className="inline-flex items-center justify-center whitespace-nowrap rounded-md text-sm ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 h-10 px-4 py-2 text-primary-foreground bg-indigo-600 hover:bg-indigo-500 font-semibold shadow-md hover:shadow-indigo-500/20">
          <Plus className="mr-2 h-4 w-4" /> Bulk Import
      </DialogTrigger>
      <DialogContent className="sm:max-w-[600px]">
        <DialogHeader>
          <DialogTitle>Import Creators</DialogTitle>
          <DialogDescription>
            Queue up creators for discovery. Our AI will automatically find their other social channels.
          </DialogDescription>
        </DialogHeader>

        <Tabs defaultValue="bulk" className="mt-4">
          <TabsList className="grid w-full grid-cols-2">
            <TabsTrigger value="bulk">Bulk Paste</TabsTrigger>
            <TabsTrigger value="single">Single Handle</TabsTrigger>
          </TabsList>
          
          <TabsContent value="bulk" className="flex flex-col gap-4 mt-4">
            <Textarea
              placeholder={`https://instagram.com/vikingbarbie\n@glamourqueen tiktok\nof:sunnyrose`}
              className="min-h-[150px] font-mono text-sm"
              value={rawText}
              onChange={(e) => setRawText(e.target.value)}
            />
            
            {finalHandles.length > 0 && (
              <div className="flex flex-col gap-2 p-3 bg-muted/30 rounded-lg border border-border/50">
                <div className="flex flex-wrap gap-2 max-h-[150px] overflow-y-auto">
                  {finalHandles.map((h, i) => (
                    <HandleChipPreview 
                      key={i} 
                      handle={h} 
                      onPlatformAssign={(p) => setAssignedPlatforms(prev => ({...prev, [i]: p}))} 
                    />
                  ))}
                </div>
                <div className="text-xs text-muted-foreground mt-2 font-medium flex gap-2">
                   <span className="text-emerald-400">{validCount} detected</span> &middot;
                   <span className="text-amber-500">{needsHintCount} need platform</span> &middot;
                   <span className="text-red-400">{duplicateCount} duplicate (skipped)</span>
                </div>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div className="flex flex-col gap-2">
                <Label>Tracking Type</Label>
                <Select value={trackingType} onValueChange={(v) => v ? setTrackingType(v) : undefined}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="unreviewed">Unreviewed</SelectItem>
                    <SelectItem value="candidate">Candidate</SelectItem>
                    <SelectItem value="inspiration">Inspiration</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="flex flex-col gap-2">
                <Label>Tags</Label>
                <Input placeholder="comma, separated" value={tags} onChange={e => setTags(e.target.value)} />
              </div>
            </div>

            <Button onClick={handleBulkSubmit} disabled={!canSubmitBulk} className="mt-2 w-full bg-indigo-600 hover:bg-indigo-500">
              {isSubmitting ? <Loader2 className="h-4 w-4 animate-spin mr-2" /> : null}
              Import {validCount} Creators
            </Button>
          </TabsContent>
          
          <TabsContent value="single" className="flex flex-col gap-4 mt-4">
             <div className="flex flex-col gap-2">
                <Label>Platform</Label>
                <Select value={singlePlatform} onValueChange={(v) => v ? setSinglePlatform(v) : undefined}>
                  <SelectTrigger><SelectValue placeholder="Select platform" /></SelectTrigger>
                  <SelectContent>
                    {Object.entries(PLATFORMS).map(([k, v]) => (
                      <SelectItem key={k} value={k}>{v.label}</SelectItem>
                    ))}
                  </SelectContent>
                </Select>
             </div>
             <div className="flex flex-col gap-2">
                <Label>Handle</Label>
                <Input placeholder="@username" value={singleHandle} onChange={e => setSingleHandle(e.target.value.replace('@',''))} />
             </div>
             <div className="flex flex-col gap-2">
                <Label>URL (Optional)</Label>
                <Input placeholder="https://..." value={singleUrl} onChange={e => setSingleUrl(e.target.value)} />
             </div>
             <Button className="mt-2 w-full bg-indigo-600 hover:bg-indigo-500">Import Creator</Button>
          </TabsContent>
        </Tabs>
      </DialogContent>
    </Dialog>
  );
}
