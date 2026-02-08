'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';
import { AlertCircle } from 'lucide-react';

export function ProblemBlock() {
  return (
    <Section id="problem" className="bg-black/50">
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="max-w-4xl mx-auto"
      >
        <motion.div variants={staggerItem} className="glass glass-hover p-8 rounded-2xl">
          <div className="flex items-start gap-4 mb-6">
            <AlertCircle className="w-6 h-6 text-accent-red flex-shrink-0 mt-1" />
            <p className="text-lg text-slate-300 leading-relaxed">{copy.problem.lead}</p>
          </div>
          
          <div className="grid md:grid-cols-2 gap-4">
            {copy.problem.bullets.map((bullet, index) => (
              <motion.div
                key={index}
                variants={staggerItem}
                className="flex items-start gap-3"
              >
                <span className="w-2 h-2 rounded-full bg-accent-red mt-2 flex-shrink-0" />
                <p className="text-slate-400">{bullet}</p>
              </motion.div>
            ))}
          </div>
          
          <motion.div
            variants={staggerItem}
            className="mt-8 pt-8 border-t border-accent-red/30"
          >
            <p className="text-lg font-semibold text-slate-100">{copy.problem.close}</p>
          </motion.div>
        </motion.div>
      </motion.div>
    </Section>
  );
}
