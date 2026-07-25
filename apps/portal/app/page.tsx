import { Footer } from "../components/Footer";
import { Header } from "../components/Header";
import { Hero } from "../components/Hero";
import { StatusCard } from "../components/StatusCard";

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
