import { ComingSoon } from "@/components/shared/ComingSoon"

export default function TikTokOutliers() {
  return (
    <ComingSoon
      phase={2}
      feature="TikTok Outliers"
      description="Posts performing 3× above their median baseline. Activates when scraping ingestion is live."
    />
  )
}
