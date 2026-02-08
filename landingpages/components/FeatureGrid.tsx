'use client';

import { Section } from './Section';
import { motion } from 'framer-motion';
import { Card } from '@/components/ui/card';
import { Code2, Database, Plug, Route, Shield, Clock } from 'lucide-react';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';

const iconMap = {
  Code2,
  Database,
  Plug,
  Route,
  Shield,
  Clock
};

export function FeatureGrid() {
  return (
    <Section id="features" title={copy.features.title}>
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto"
      >
        {copy.features.items.map((feature, index) => {
          const IconComponent = iconMap[feature.icon as keyof typeof iconMap] || Code2;
          return (
            <motion.div key={index} variants={staggerItem}>
              <Card className="glass glass-hover p-6 h-full">
                <IconComponent className="w-8 h-8 text-accent-red mb-4" />
                <h3 className="text-lg font-semibold text-slate-100 mb-2">{feature.name}</h3>
                <p className="text-sm text-slate-400">{feature.desc}</p>
              </Card>
            </motion.div>
          );
        })}
      </motion.div>
    </Section>
  );
}
