import { Nav } from "@/components/nav";
import { NotFoundPage } from "@/components/not-found-page";
import { Footer } from "@/components/footer";

export default function NotFound() {
  return (
    <>
      <Nav />
      <main>
        <NotFoundPage />
      </main>
      <Footer />
    </>
  );
}
