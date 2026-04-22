export default function AdminPage() {
  return (
    <div className="flex flex-col gap-6 w-full h-[80vh] items-center justify-center text-center">
       <div className="p-10 border border-dashed border-border/50 rounded-2xl bg-muted/10 w-full max-w-lg">
          <h1 className="text-2xl font-bold tracking-tight mb-2">Ops Admin</h1>
          <p className="text-muted-foreground">Workspace settings, billing, integrations, and user permissions will be managed here.</p>
       </div>
    </div>
  );
}
