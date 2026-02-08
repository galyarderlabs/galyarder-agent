'use client';

import { Section } from './Section';
import { Accordion, AccordionContent, AccordionItem, AccordionTrigger } from '@/components/ui/accordion';
import { copy } from '@/lib/copy';

export function FAQ() {
  return (
    <Section id="faq" title={copy.faq.title} className="bg-black/30">
      <div className="max-w-3xl mx-auto">
        <Accordion type="single" collapsible className="w-full">
          {copy.faq.items.map((item, index) => (
            <AccordionItem key={index} value={`item-${index}`} className="border-slate-800">
              <AccordionTrigger className="text-left text-slate-100 hover:text-slate-300">
                {item.q}
              </AccordionTrigger>
              <AccordionContent className="text-slate-400">
                {item.a}
              </AccordionContent>
            </AccordionItem>
          ))}
        </Accordion>
      </div>
    </Section>
  );
}
