'use client';

import { motion } from 'framer-motion';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { copy } from '@/lib/copy';
import { staggerContainer, staggerItem } from '@/lib/motion';
import { ChevronDown, Zap, Shield, Cpu } from 'lucide-react';
import { HeroVisual } from './HeroVisual';

export function Hero() {
  return (
    <section className="relative min-h-screen flex items-center justify-center pt-20 overflow-hidden">
      {/* Animated background visual */}
      <HeroVisual />
      
      <div className="container-section text-center relative z-10">
        <motion.div
          variants={staggerContainer}
          initial="initial"
          animate="animate"
          className="max-w-5xl mx-auto"
        >
          {/* Trust badges */}
          <motion.div
            variants={staggerItem}
            className="flex items-center justify-center gap-4 mb-8"
          >
            <Badge variant="outline" className="border-green-500/50 text-green-400">
              <Zap className="w-3 h-3 mr-1" />
              Live Now
            </Badge>
            <Badge variant="outline" className="border-blue-500/50 text-blue-400">
              <Shield className="w-3 h-3 mr-1" />
              SOC2 Compliant
            </Badge>
            <Badge variant="outline" className="border-purple-500/50 text-purple-400">
              <Cpu className="w-3 h-3 mr-1" />
              Self-Hosted
            </Badge>
          </motion.div>
          
          <motion.p
            variants={staggerItem}
            className="text-sm font-medium text-accent-red uppercase tracking-wider mb-6"
          >
            {copy.hero.kicker}
          </motion.p>
          
          <motion.h1
            variants={staggerItem}
            className="text-5xl md:text-6xl lg:text-8xl font-bold mb-6"
          >
            <span className="text-gradient">Stop Prompting.</span>
            <br />
            <span className="text-slate-100">Start Executing.</span>
          </motion.h1>
          
          <motion.p
            variants={staggerItem}
            className="text-lg md:text-xl text-slate-300 mb-6 max-w-3xl mx-auto leading-relaxed"
          >
            GalyarderAgent transforms AI from a <span className="text-accent-red font-semibold">chatbot</span> into an{' '}
            <span className="text-accent-red font-semibold">execution engine</span>. Protocol-driven, memory-aware, and 
            built for teams that ship—not teams that prompt.
          </motion.p>
          
          {/* Stats row */}
          <motion.div
            variants={staggerItem}
            className="grid grid-cols-3 gap-8 max-w-2xl mx-auto mb-10"
          >
            <div>
              <div className="text-3xl font-bold text-slate-100">10x</div>
              <div className="text-sm text-slate-500">Faster Execution</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-slate-100">100%</div>
              <div className="text-sm text-slate-500">Auditable</div>
            </div>
            <div>
              <div className="text-3xl font-bold text-slate-100">0</div>
              <div className="text-sm text-slate-500">Vendor Lock-in</div>
            </div>
          </motion.div>
          
          <motion.div
            variants={staggerItem}
            className="flex flex-col sm:flex-row gap-4 justify-center mb-8"
          >
            <Button
              asChild
              size="lg"
              className="bg-accent-red hover:bg-accent-red/90 text-white px-10 py-6 text-lg shadow-lg shadow-accent-red/20 hover:shadow-xl hover:shadow-accent-red/30 transition-all"
            >
              <a href="#access">
                Start Building Now
                <span className="ml-2">→</span>
              </a>
            </Button>
            <Button
              asChild
              size="lg"
              variant="outline"
              className="border-slate-700 text-slate-300 hover:bg-slate-800/50 px-8 py-6 text-lg"
            >
              <a href="#demo">Watch 2-Min Demo</a>
            </Button>
          </motion.div>
          
          {/* Social proof */}
          <motion.div
            variants={staggerItem}
            className="flex items-center justify-center gap-2 text-sm text-slate-500"
          >
            <div className="flex -space-x-2">
              {[1, 2, 3, 4, 5].map((i) => (
                <div
                  key={i}
                  className="w-8 h-8 rounded-full bg-gradient-to-br from-slate-600 to-slate-800 border-2 border-slate-900"
                />
              ))}
            </div>
            <span>
              Join <span className="text-slate-300 font-semibold">500+ engineers</span> building with GalyarderAgent
            </span>
          </motion.div>
        </motion.div>
      </div>
      
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        transition={{ delay: 2, duration: 1 }}
        className="absolute bottom-8 left-1/2 transform -translate-x-1/2 z-10"
      >
        <a href="#problem" className="text-slate-500 hover:text-slate-300 transition-colors">
          <ChevronDown className="w-6 h-6 animate-bounce" />
        </a>
      </motion.div>
    </section>
  );
}
