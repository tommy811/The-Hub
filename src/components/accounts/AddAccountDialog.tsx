"use client";

import { useState } from "react";
import { Plus, Camera, MonitorPlay } from "lucide-react";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle, DialogTrigger } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Label } from "@/components/ui/label";

export function AddAccountDialog() {
  const [handle, setHandle] = useState("");
  const [platform, setPlatform] = useState("instagram");
  const [trackingType, setTrackingType] = useState("unreviewed");

  const cleanHandle = handle.replace('@', '').trim();

  return (
    <Dialog>
      <DialogTrigger className="inline-flex items-center justify-center whitespace-nowrap text-sm font-medium transition-colors focus-visible:outline-none focus-visible:ring-1 disabled:pointer-events-none disabled:opacity-50 text-primary-foreground fixed bottom-8 right-8 h-14 w-14 rounded-full shadow-2xl hover:shadow-indigo-500/25 bg-indigo-600 hover:bg-indigo-500 hover:scale-105 z-50">
          <Plus className="h-6 w-6" />
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Track New Account</DialogTitle>
          <DialogDescription>
            Add a profile to begin data ingestion. We&apos;ll queue a scrape immediately via Apify.
          </DialogDescription>
        </DialogHeader>
        
        <div className="grid gap-4 py-4">
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="platform" className="text-right">Platform</Label>
            <div className="col-span-3">
               <Select value={platform} onValueChange={(v) => v ? setPlatform(v) : undefined}>
                 <SelectTrigger>
                   <SelectValue placeholder="Select platform" />
                 </SelectTrigger>
                 <SelectContent>
                   <SelectItem value="instagram"><span className="flex items-center gap-2"><Camera className="h-4 w-4"/> Instagram</span></SelectItem>
                   <SelectItem value="tiktok"><span className="flex items-center gap-2"><MonitorPlay className="h-4 w-4"/> TikTok</span></SelectItem>
                 </SelectContent>
               </Select>
            </div>
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="handle" className="text-right">Username</Label>
            <Input 
              id="handle" 
              placeholder="@username" 
              className="col-span-3 font-mono" 
              value={handle}
              onChange={(e) => setHandle(e.target.value)}
            />
          </div>

          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="tracking" className="text-right">Tracking</Label>
            <div className="col-span-3">
               <Select value={trackingType} onValueChange={(v) => v ? setTrackingType(v) : undefined}>
                 <SelectTrigger>
                   <SelectValue placeholder="Tracking Type" />
                 </SelectTrigger>
                 <SelectContent>
                   <SelectItem value="managed">Managed</SelectItem>
                   <SelectItem value="inspiration">Inspiration</SelectItem>
                   <SelectItem value="competitor">Competitor</SelectItem>
                   <SelectItem value="candidate">Candidate</SelectItem>
                   <SelectItem value="hybrid_ai">Hybrid AI</SelectItem>
                   <SelectItem value="coach">Coach</SelectItem>
                   <SelectItem value="unreviewed">Unreviewed</SelectItem>
                 </SelectContent>
               </Select>
            </div>
          </div>
          
          <div className="grid grid-cols-4 items-center gap-4">
            <Label htmlFor="tags" className="text-right">Tags</Label>
            <Input id="tags" placeholder="comma, separated" className="col-span-3" />
          </div>

        </div>
        <DialogFooter>
          <Button type="submit" onClick={() => console.log('submitting', cleanHandle)}>Add & Scrape Data</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
