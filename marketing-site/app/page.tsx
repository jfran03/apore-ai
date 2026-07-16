import { Nav } from "@/components/nav";
import { Hero } from "@/components/hero";
import { AudienceGrid } from "@/components/audience-grid";
import { ProblemBand } from "@/components/problem-band";
import { PlatformFeatures } from "@/components/platform-features";
import { SystemLoop } from "@/components/system-loop";
import { ProductMockup } from "@/components/product-mockup";
import { ResearchBand } from "@/components/research-band";
import { Footer } from "@/components/footer";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <AudienceGrid />
        <ProblemBand />
        <PlatformFeatures />
        <SystemLoop />
        <ProductMockup />
        <ResearchBand />
      </main>
      <Footer />
    </>
  );
}
