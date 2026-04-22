export default function OutliersPage() {
  return (
    <div className="flex flex-col gap-6 w-full h-[80vh] items-center justify-center text-center">
       <div className="p-10 border border-dashed border-border/50 rounded-2xl bg-muted/10 w-full max-w-lg">
          <h1 className="text-2xl font-bold tracking-tight mb-2">Instagram Outliers</h1>
          <p className="text-muted-foreground">This view will contain the outlier analysis and trending detection models.</p>
       </div>
    </div>
  );
}
