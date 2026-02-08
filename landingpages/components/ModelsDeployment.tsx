'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { Cpu, Check } from 'lucide-react';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';

export function ModelsDeployment() {
  return (
    <Section id="models" title={copy.models.title}>
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="max-w-3xl mx-auto"
      >
        <div className="glass p-8 rounded-2xl">
          <Cpu className="w-12 h-12 text-accent-red mb-6 mx-auto" />
          <ul className="space-y-4">
            {copy.models.bullets.map((bullet, index) => (
              <motion.li
                key={index}
                variants={staggerItem}
                className="flex items-start gap-3"
              >
                <Check className="w-5 h-5 text-blue-500 flex-shrink-0 mt-0.5" />
                <span className="text-slate-300">{bullet}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      </motion.div>
    </Section>
  );
}
