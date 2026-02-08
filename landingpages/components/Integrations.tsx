'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { ExternalLink } from 'lucide-react';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';

export function Integrations() {
  return (
    <Section id="integrations" title={copy.integrations.title} className="bg-black/30">
      <p className="text-center text-slate-400 mb-12 max-w-2xl mx-auto">
        {copy.integrations.note}
      </p>
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto"
      >
        {copy.integrations.systems.map((system, index) => (
          <motion.div key={index} variants={staggerItem}>
            <a
              href={system.link}
              target="_blank"
              rel="noopener noreferrer"
              className="block h-full"
            >
              <Card className="glass glass-hover p-6 h-full">
                <div className="flex items-start justify-between mb-3">
                  <h3 className="text-lg font-semibold text-slate-100">{system.name}</h3>
                  <ExternalLink className="w-4 h-4 text-slate-500" />
                </div>
                <p className="text-sm text-slate-400">{system.desc}</p>
              </Card>
            </a>
          </motion.div>
        ))}
      </motion.div>
    </Section>
  );
}
