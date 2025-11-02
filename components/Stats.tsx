'use client';

import { motion } from 'framer-motion';
import { Section } from './Section';
import { Card } from '@/components/ui/card';
import { TrendingUp, Users, Zap, Shield } from 'lucide-react';
import { staggerContainer, staggerItem } from '@/lib/motion';

const stats = [
  {
    icon: TrendingUp,
    value: '2.5M+',
    label: 'Protocols Executed',
    change: '+85% this month',
    color: 'text-green-500',
  },
  {
    icon: Users,
    value: '10K+',
    label: 'Active Teams',
    change: 'Across 50+ countries',
    color: 'text-blue-500',
  },
  {
    icon: Zap,
    value: '99.9%',
    label: 'Uptime SLA',
    change: 'Zero downtime in 6 months',
    color: 'text-purple-500',
  },
  {
    icon: Shield,
    value: '100%',
    label: 'Audit Success',
    change: 'Every action traceable',
    color: 'text-accent-red',
  },
];

export function Stats() {
  return (
    <Section 
      id="stats" 
      className="bg-black/30 relative overflow-hidden"
    >
      {/* Background decoration */}
      <div className="absolute inset-0">
        <div className="absolute top-0 left-1/3 w-96 h-96 bg-accent-red/5 rounded-full filter blur-3xl" />
        <div className="absolute bottom-0 right-1/3 w-96 h-96 bg-blue-500/5 rounded-full filter blur-3xl" />
      </div>

      <div className="relative z-10">
        <div className="text-center mb-12">
          <h2 className="text-3xl md:text-4xl font-bold text-slate-100 mb-4">
            Built for Scale. Proven in Production.
          </h2>
          <p className="text-lg text-slate-400 max-w-2xl mx-auto">
            Real teams. Real execution. Real results.
          </p>
        </div>

        <motion.div
          variants={staggerContainer}
          initial="initial"
          whileInView="animate"
          viewport={{ once: true }}
          className="grid md:grid-cols-2 lg:grid-cols-4 gap-6 max-w-6xl mx-auto"
        >
          {stats.map((stat, index) => {
            const Icon = stat.icon;
            return (
              <motion.div key={index} variants={staggerItem}>
                <Card className="glass glass-hover p-6 text-center relative group">
                  <div className="absolute inset-0 bg-gradient-to-br from-transparent to-slate-900/50 rounded-xl opacity-0 group-hover:opacity-100 transition-opacity" />
                  
                  <div className="relative z-10">
                    <Icon className={`w-8 h-8 ${stat.color} mx-auto mb-4`} />
                    <div className="text-3xl font-bold text-slate-100 mb-2">
                      {stat.value}
                    </div>
                    <div className="text-sm text-slate-400 mb-2">
                      {stat.label}
                    </div>
                    <div className={`text-xs ${stat.color} opacity-80`}>
                      {stat.change}
                    </div>
                  </div>
                </Card>
              </motion.div>
            );
          })}
        </motion.div>
      </div>
    </Section>
  );
}
