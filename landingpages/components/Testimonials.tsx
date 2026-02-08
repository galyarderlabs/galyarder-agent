'use client';

import { motion } from 'framer-motion';
import { Section } from './Section';
import { Card } from '@/components/ui/card';
import { Star, Twitter, Github, Linkedin } from 'lucide-react';
import { staggerContainer, staggerItem } from '@/lib/motion';

const testimonials = [
  {
    name: 'Alex Chen',
    role: 'CTO at TechFlow',
    avatar: 'AC',
    content: 'Finally, an AI that actually executes instead of just suggesting. Cut our deployment time by 80%. This is what we\'ve been waiting for.',
    rating: 5,
    platform: 'twitter',
  },
  {
    name: 'Sarah Rodriguez',
    role: 'Engineering Lead at Scale',
    avatar: 'SR',
    content: 'The protocol DSL is genius. We replaced 10,000 lines of automation scripts with 500 lines of protocols. Game changer.',
    rating: 5,
    platform: 'github',
  },
  {
    name: 'Marcus Wei',
    role: 'Founder at AutomateIO',
    avatar: 'MW',
    content: 'Local-first, BYOK models, full audit trails. GalyarderAgent respects sovereignty like no other platform. Our compliance team loves it.',
    rating: 5,
    platform: 'linkedin',
  },
  {
    name: 'Emily Johnson',
    role: 'DevOps Engineer at CloudNative',
    avatar: 'EJ',
    content: 'Sentinel mode caught 3 critical issues before they hit production. It\'s like having a senior engineer watching 24/7.',
    rating: 5,
    platform: 'twitter',
  },
  {
    name: 'David Park',
    role: 'VP Engineering at FinTech Corp',
    avatar: 'DP',
    content: 'The memory graph is revolutionary. Context that actually persists across sessions without hallucinations. Incredible.',
    rating: 5,
    platform: 'github',
  },
  {
    name: 'Lisa Thompson',
    role: 'Principal Architect at DataPro',
    avatar: 'LT',
    content: 'We run 1000+ protocols daily. Zero vendor lock-in, complete control. This is how AI automation should work.',
    rating: 5,
    platform: 'linkedin',
  },
];

const PlatformIcon = ({ platform }: { platform: string }) => {
  switch (platform) {
    case 'twitter':
      return <Twitter className="w-4 h-4 text-blue-400" />;
    case 'github':
      return <Github className="w-4 h-4 text-slate-400" />;
    case 'linkedin':
      return <Linkedin className="w-4 h-4 text-blue-600" />;
    default:
      return null;
  }
};

export function Testimonials() {
  return (
    <Section 
      id="testimonials" 
      title="Loved by Engineers Who Ship"
      subtitle="Real feedback from teams using GalyarderAgent in production"
    >
      <motion.div
        variants={staggerContainer}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="grid md:grid-cols-2 lg:grid-cols-3 gap-6 max-w-6xl mx-auto"
      >
        {testimonials.map((testimonial, index) => (
          <motion.div key={index} variants={staggerItem}>
            <Card className="glass glass-hover p-6 h-full flex flex-col">
              <div className="flex items-start justify-between mb-4">
                <div className="flex items-center gap-3">
                  <div className="w-12 h-12 rounded-full bg-gradient-to-br from-slate-600 to-slate-800 flex items-center justify-center text-sm font-bold text-slate-200">
                    {testimonial.avatar}
                  </div>
                  <div>
                    <div className="font-semibold text-slate-100">
                      {testimonial.name}
                    </div>
                    <div className="text-xs text-slate-500">
                      {testimonial.role}
                    </div>
                  </div>
                </div>
                <PlatformIcon platform={testimonial.platform} />
              </div>

              <div className="flex gap-0.5 mb-3">
                {[...Array(testimonial.rating)].map((_, i) => (
                  <Star key={i} className="w-4 h-4 fill-yellow-500 text-yellow-500" />
                ))}
              </div>

              <p className="text-sm text-slate-300 leading-relaxed flex-grow">
                &ldquo;{testimonial.content}&rdquo;
              </p>
            </Card>
          </motion.div>
        ))}
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        whileInView={{ opacity: 1, y: 0 }}
        viewport={{ once: true }}
        transition={{ delay: 0.5 }}
        className="text-center mt-12"
      >
        <div className="inline-flex items-center gap-2 text-sm text-slate-500">
          <Star className="w-4 h-4 fill-yellow-500 text-yellow-500" />
          <span>4.9/5 from 500+ reviews</span>
        </div>
      </motion.div>
    </Section>
  );
}
