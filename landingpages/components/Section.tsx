'use client';

import { cn } from '@/lib/utils';
import { motion } from 'framer-motion';
import { fadeInUp } from '@/lib/motion';

interface SectionProps {
  id?: string;
  kicker?: string;
  title?: string;
  subtitle?: string;
  children: React.ReactNode;
  className?: string;
  containerClassName?: string;
}

export function Section({
  id,
  kicker,
  title,
  subtitle,
  children,
  className,
  containerClassName,
}: SectionProps) {
  return (
    <section id={id} className={cn('py-16 md:py-24 lg:py-32', className)}>
      <div className={cn('container-section', containerClassName)}>
        {(kicker || title || subtitle) && (
          <motion.div
            variants={fadeInUp}
            initial="initial"
            whileInView="animate"
            viewport={{ once: true }}
            className="text-center mb-12 md:mb-16"
          >
            {kicker && (
              <p className="text-sm font-medium text-accent-red uppercase tracking-wider mb-4">
                {kicker}
              </p>
            )}
            {title && (
              <h2 className="text-3xl md:text-4xl lg:text-5xl font-bold text-slate-100 mb-4">
                {title}
              </h2>
            )}
            {subtitle && (
              <p className="text-lg text-slate-400 max-w-3xl mx-auto">
                {subtitle}
              </p>
            )}
          </motion.div>
        )}
        {children}
      </div>
    </section>
  );
}
