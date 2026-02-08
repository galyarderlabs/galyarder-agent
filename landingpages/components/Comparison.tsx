'use client';

import { motion } from 'framer-motion';
import { Section } from './Section';
import { Check, X, Minus } from 'lucide-react';
import { fadeInUp } from '@/lib/motion';

const features = [
  'Protocol-driven execution',
  'Local-first deployment',
  'BYOK models',
  'Full audit trail',
  'Memory persistence',
  'Human-in-the-loop',
  'Deterministic execution',
  'No vendor lock-in',
  'Self-hosted option',
  'Code ownership',
  'Rollback capability',
  'Cost transparency',
];

const competitors: Array<{
  name: string;
  type: string;
  features: Array<boolean | string>;
  highlight: boolean;
}> = [
  {
    name: 'GalyarderAgent',
    type: 'Execution Engine',
    features: [true, true, true, true, true, true, true, true, true, true, true, true],
    highlight: true,
  },
  {
    name: 'ChatGPT Plus',
    type: 'Chat Interface',
    features: [false, false, false, false, 'partial', false, false, false, false, false, false, false],
    highlight: false,
  },
  {
    name: 'GitHub Copilot',
    type: 'Code Assistant',
    features: [false, false, false, false, false, false, false, false, false, true, false, 'partial'],
    highlight: false,
  },
  {
    name: 'AutoGPT',
    type: 'Autonomous Agent',
    features: ['partial', true, 'partial', 'partial', 'partial', false, false, 'partial', true, true, false, true],
    highlight: false,
  },
];

const FeatureIcon = ({ value }: { value: boolean | string }) => {
  if (value === true) {
    return <Check className="w-5 h-5 text-green-500" />;
  } else if (value === false) {
    return <X className="w-5 h-5 text-slate-600" />;
  } else {
    return <Minus className="w-5 h-5 text-yellow-500" />;
  }
};

export function Comparison() {
  return (
    <Section 
      id="comparison" 
      title="Built Different. By Design."
      subtitle="See why teams choose GalyarderAgent over chat-first alternatives"
      className="overflow-x-auto"
    >
      <motion.div
        variants={fadeInUp}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="max-w-6xl mx-auto"
      >
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr>
                <th className="text-left p-4 text-sm font-medium text-slate-400">Feature</th>
                {competitors.map((competitor, index) => (
                  <th key={index} className="text-center p-4 min-w-[150px]">
                    <div className={`${competitor.highlight ? 'text-accent-red' : 'text-slate-300'}`}>
                      <div className="font-semibold text-sm">{competitor.name}</div>
                      <div className="text-xs text-slate-500 mt-1">{competitor.type}</div>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {features.map((feature, featureIndex) => (
                <motion.tr
                  key={featureIndex}
                  initial={{ opacity: 0, x: -20 }}
                  whileInView={{ opacity: 1, x: 0 }}
                  viewport={{ once: true }}
                  transition={{ delay: featureIndex * 0.05 }}
                  className="border-t border-slate-800 hover:bg-slate-900/30 transition-colors"
                >
                  <td className="p-4 text-sm text-slate-300">{feature}</td>
                  {competitors.map((competitor, competitorIndex) => (
                    <td key={competitorIndex} className="text-center p-4">
                      <div className={`inline-flex items-center justify-center ${
                        competitor.highlight ? 'scale-110' : ''
                      }`}>
                        <FeatureIcon value={competitor.features[featureIndex] || false} />
                      </div>
                    </td>
                  ))}
                </motion.tr>
              ))}
            </tbody>
          </table>
        </div>

        <motion.div
          initial={{ opacity: 0, y: 20 }}
          whileInView={{ opacity: 1, y: 0 }}
          viewport={{ once: true }}
          transition={{ delay: 0.5 }}
          className="mt-8 p-6 glass rounded-xl border border-accent-red/30"
        >
          <div className="flex items-center justify-between flex-wrap gap-4">
            <div>
              <h3 className="text-lg font-semibold text-slate-100 mb-2">
                Stop choosing between control and capability
              </h3>
              <p className="text-sm text-slate-400">
                GalyarderAgent gives you both: powerful AI execution with complete sovereignty.
              </p>
            </div>
            <a
              href="#access"
              className="inline-flex items-center gap-2 px-6 py-3 bg-accent-red hover:bg-accent-red/90 text-white rounded-lg transition-colors"
            >
              Start Building
              <span>→</span>
            </a>
          </div>
        </motion.div>
      </motion.div>
    </Section>
  );
}
