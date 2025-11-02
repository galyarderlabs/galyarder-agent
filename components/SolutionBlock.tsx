'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';
import { CheckCircle } from 'lucide-react';

export function SolutionBlock() {
  return (
    <Section id="solution" title={copy.solution.title}>
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="max-w-4xl mx-auto"
      >
        <motion.p
          variants={staggerItem}
          className="text-lg text-slate-300 text-center mb-12"
        >
          {copy.solution.body}
        </motion.p>
        
        <motion.div
          variants={staggerContainer}
          className="grid md:grid-cols-3 gap-6"
        >
          {copy.solution.outcomes.map((outcome, index) => (
            <motion.div
              key={index}
              variants={staggerItem}
              className="glass glass-hover p-6 rounded-xl"
            >
              <CheckCircle className="w-5 h-5 text-green-500 mb-3" />
              <p className="text-slate-300">{outcome}</p>
            </motion.div>
          ))}
        </motion.div>
      </motion.div>
    </Section>
  );
}
