'use client';

import { useState } from 'react';
import { Section } from './Section';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Checkbox } from '@/components/ui/checkbox';
import { Card } from '@/components/ui/card';
import { copy } from '@/lib/copy';
import { toast } from 'sonner';
import { motion } from 'framer-motion';
import { fadeInUp } from '@/lib/motion';

export function WaitlistForm() {
  const [loading, setLoading] = useState(false);
  const [email, setEmail] = useState('');
  const [role, setRole] = useState('');
  const [consent, setConsent] = useState(false);
  const [honeypot, setHoneypot] = useState('');

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    
    // Bot check
    if (honeypot) return;
    
    if (!consent) {
      toast.error('Please agree to receive communications');
      return;
    }

    setLoading(true);

    try {
      const response = await fetch('/api/waitlist', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, role, consent }),
      });

      if (response.ok) {
        toast.success(copy.waitlist.success);
        setEmail('');
        setRole('');
        setConsent(false);
      } else {
        toast.error(copy.waitlist.error);
      }
    } catch {
      toast.error(copy.waitlist.error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Section id="access" title={copy.waitlist.title}>
      <motion.div
        variants={fadeInUp}
        initial="initial"
        whileInView="animate"
        viewport={{ once: true }}
        className="max-w-xl mx-auto"
      >
        <p className="text-center text-slate-400 mb-8">
          {copy.waitlist.body}
        </p>
        
        <Card className="glass p-8">
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <Label htmlFor="email" className="text-slate-200">
                {copy.waitlist.emailLabel}
              </Label>
              <Input
                id="email"
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder={copy.waitlist.emailPlaceholder}
                className="mt-2 bg-black/50 border-slate-700 text-slate-100 placeholder:text-slate-500"
              />
            </div>

            <div>
              <Label htmlFor="role" className="text-slate-200">
                {copy.waitlist.roleLabel}
              </Label>
              <Input
                id="role"
                type="text"
                value={role}
                onChange={(e) => setRole(e.target.value)}
                placeholder={copy.waitlist.rolePlaceholder}
                className="mt-2 bg-black/50 border-slate-700 text-slate-100 placeholder:text-slate-500"
              />
            </div>

            {/* Honeypot field */}
            <div className="hidden">
              <Input
                type="text"
                value={honeypot}
                onChange={(e) => setHoneypot(e.target.value)}
                tabIndex={-1}
                autoComplete="off"
              />
            </div>

            <div className="flex items-start space-x-2">
              <Checkbox
                id="consent"
                checked={consent}
                onCheckedChange={(checked) => setConsent(checked as boolean)}
                className="mt-1"
              />
              <Label htmlFor="consent" className="text-sm text-slate-400 cursor-pointer">
                {copy.waitlist.consentLabel}
              </Label>
            </div>

            <Button
              type="submit"
              disabled={loading}
              className="w-full bg-accent-red hover:bg-accent-red/90 text-white"
            >
              {loading ? 'Submitting...' : copy.waitlist.cta}
            </Button>

            <p className="text-xs text-slate-500 text-center">
              {copy.waitlist.legal}
            </p>
          </form>
        </Card>
      </motion.div>
    </Section>
  );
}
