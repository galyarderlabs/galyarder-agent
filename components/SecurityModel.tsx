'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { Shield, Check } from 'lucide-react';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';

export function SecurityModel() {
  return (
    <Section id="security" title={copy.security.title} className="bg-black/30">
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="max-w-3xl mx-auto"
      >
        <div className="glass p-8 rounded-2xl">
          <Shield className="w-12 h-12 text-accent-red mb-6 mx-auto" />
          <ul className="space-y-4">
            {copy.security.bullets.map((bullet, index) => (
              <motion.li
                key={index}
                variants={staggerItem}
                className="flex items-start gap-3"
              >
                <Check className="w-5 h-5 text-green-500 flex-shrink-0 mt-0.5" />
                <span className="text-slate-300">{bullet}</span>
              </motion.li>
            ))}
          </ul>
        </div>
      </motion.div>
    </Section>
  );
}
