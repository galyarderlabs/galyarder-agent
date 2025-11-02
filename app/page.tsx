'use client';

import { Header } from '@/components/Header';
import { Hero } from '@/components/Hero';
import { Stats } from '@/components/Stats';
import { ProblemBlock } from '@/components/ProblemBlock';
import { SolutionBlock } from '@/components/SolutionBlock';
import { HowItWorks } from '@/components/HowItWorks';
import { Comparison } from '@/components/Comparison';
import { Modes } from '@/components/Modes';
import { Integrations } from '@/components/Integrations';
import { FeatureGrid } from '@/components/FeatureGrid';
import { Testimonials } from '@/components/Testimonials';
import { SecurityModel } from '@/components/SecurityModel';
import { ModelsDeployment } from '@/components/ModelsDeployment';
import { FAQ } from '@/components/FAQ';
import { WaitlistForm } from '@/components/WaitlistForm';
import { Footer } from '@/components/Footer';

export default function Home() {
  return (
    <>
      <Header />
      <main id="main">
        <Hero />
        <Stats />
        <ProblemBlock />
        <SolutionBlock />
        <HowItWorks />
        <Comparison />
        <Modes />
        <Integrations />
        <FeatureGrid />
        <Testimonials />
        <SecurityModel />
        <ModelsDeployment />
        <FAQ />
        <WaitlistForm />
      </main>
      <Footer />
    </>
  );
}
