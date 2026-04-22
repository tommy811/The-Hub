export default function ContentHubPage() {
  return (
    <div className="flex flex-col gap-6 w-full h-[80vh] items-center justify-center text-center">
       <div className="p-10 border border-dashed border-border/50 rounded-2xl bg-muted/10 w-full max-w-lg">
          <h1 className="text-2xl font-bold tracking-tight mb-2">Content Hub</h1>
          <p className="text-muted-foreground">This module is part of the v2 scope for Agency Command Center. Content lifecycle and approval workflows will be managed here.</p>
       </div>
    </div>
  );
}
