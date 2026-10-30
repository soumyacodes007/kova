import { Footer, Hero, HowItWorks, Nav, Next, Proof, RunIt, Statement, ZeroScore } from "@/components/landing/sections";

export default function Home() {
  return (
    <>
      <Nav />
      <main>
        <Hero />
        <Statement />
        <ZeroScore />
        <HowItWorks />
        <Proof />
        <RunIt />
        <Next />
      </main>
      <Footer />
    </>
  );
}
