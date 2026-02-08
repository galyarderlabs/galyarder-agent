'use client';

import { useState } from 'react';
import { motion } from 'framer-motion';
import { Menu } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Sheet, SheetContent, SheetTrigger } from '@/components/ui/sheet';
import { copy } from '@/lib/copy';

export function Header() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.5 }}
      className="fixed top-0 left-0 right-0 z-50 bg-black/50 backdrop-blur-md border-b border-white/10"
    >
      <div className="container-section">
        <div className="flex items-center justify-between h-16 md:h-20">
          <div className="font-bold text-xl text-slate-100">
            GalyarderAgent
          </div>

          {/* Desktop Navigation */}
          <nav className="hidden lg:flex items-center gap-8">
            {copy.nav.map((item) => (
              <a
                key={item.href}
                href={item.href}
                className="text-sm text-slate-300 hover:text-slate-100 transition-colors"
              >
                {item.label}
              </a>
            ))}
            <Button
              asChild
              className="bg-accent-red hover:bg-accent-red/90 text-white"
            >
              <a href="#access">{copy.hero.ctaPrimary}</a>
            </Button>
          </nav>

          {/* Mobile Navigation */}
          <Sheet open={isOpen} onOpenChange={setIsOpen}>
            <SheetTrigger asChild className="lg:hidden">
              <Button variant="ghost" size="icon">
                <Menu className="h-5 w-5" />
              </Button>
            </SheetTrigger>
            <SheetContent side="right" className="bg-black/95 border-white/10">
              <nav className="flex flex-col gap-4 mt-8">
                {copy.nav.map((item) => (
                  <a
                    key={item.href}
                    href={item.href}
                    onClick={() => setIsOpen(false)}
                    className="text-lg text-slate-300 hover:text-slate-100 transition-colors py-2"
                  >
                    {item.label}
                  </a>
                ))}
                <Button
                  asChild
                  className="bg-accent-red hover:bg-accent-red/90 text-white w-full mt-4"
                >
                  <a href="#access" onClick={() => setIsOpen(false)}>
                    {copy.hero.ctaPrimary}
                  </a>
                </Button>
              </nav>
            </SheetContent>
          </Sheet>
        </div>
      </div>
    </motion.header>
  );
}
