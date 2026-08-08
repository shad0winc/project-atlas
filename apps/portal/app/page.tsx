import { Footer } from "../components/layout/Footer";
import { Header } from "../components/layout/Header";

import { Hero } from "../components/home/Hero";
import { StatusCard } from "../components/home/StatusCard";

export default function HomePage(): React.ReactElement {
  return (
    <div className="page-shell">
      <Header />
      <Hero />
      <StatusCard />
      <Footer />
    </div>
  );
}
