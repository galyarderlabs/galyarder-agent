'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';

export function HowItWorks() {
  return (
    <Section id="how" title={copy.how.title} className="bg-black/30">
      <motion.ol
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="grid md:grid-cols-3 gap-8 max-w-5xl mx-auto"
      >
        {copy.how.steps.map((step, index) => (
          <motion.li key={index} variants={staggerItem}>
            <Card className="glass glass-hover p-6 h-full relative">
              <div className="absolute -top-3 -left-3 w-8 h-8 bg-accent-red rounded-full flex items-center justify-center text-white font-bold">
                {index + 1}
              </div>
              <h3 className="text-xl font-semibold text-slate-100 mb-3">{step.title}</h3>
              <p className="text-slate-400">{step.body}</p>
            </Card>
          </motion.li>
        ))}
      </motion.ol>
    </Section>
  );
}
