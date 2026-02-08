'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';

const modeColors = {
  Prime: 'bg-blue-500/20 text-blue-300 border-blue-500/50',
  Architekt: 'bg-purple-500/20 text-purple-300 border-purple-500/50',
  Oracle: 'bg-green-500/20 text-green-300 border-green-500/50',
  Sentinel: 'bg-orange-500/20 text-orange-300 border-orange-500/50',
};

export function Modes() {
  return (
    <Section id="modes" title={copy.modes.title} subtitle={copy.modes.body}>
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto"
      >
        {copy.modes.items.map((mode, index) => (
          <motion.div key={index} variants={staggerItem}>
            <Card className="glass glass-hover p-6 h-full">
              <Badge 
                className={`mb-4 ${modeColors[mode.name as keyof typeof modeColors]}`}
                variant="outline"
              >
                {mode.name}
              </Badge>
              <p className="text-sm text-slate-400">{mode.desc}</p>
            </Card>
          </motion.div>
        ))}
      </motion.div>
      <motion.p
        variants={staggerItem}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="text-center text-sm text-slate-500 mt-8 max-w-3xl mx-auto"
      >
        {copy.modes.note}
      </motion.p>
    </Section>
  );
}
