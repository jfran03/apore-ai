import type { Metadata } from "next";
import { Nav } from "@/components/nav";
import { Manifesto } from "@/components/manifesto";
import { Footer } from "@/components/footer";

export const metadata: Metadata = {
  title: "Manifesto",
  description:
    "Productive struggle is the signal. How Apore calibrates Socratic tutoring to the zone where learning actually happens.",
};

export default function ManifestoPage() {
  return (
    <>
      <Nav variant="light" />
      <main>
        <Manifesto />
      </main>
      <Footer />
    </>
  );
}
