import { z } from 'zod';

export const waitlistSchema = z.object({
  email: z
    .string()
    .email('Please enter a valid email address')
    .toLowerCase()
    .trim(),
  role: z
    .enum(['Builder', 'Operator', 'Researcher'])
    .optional(),
  consent: z
    .boolean()
    .refine((val) => val === true, {
      message: 'You must agree to receive communications',
    }),
  honeypot: z.string().optional(),
});

export type WaitlistPayload = z.infer<typeof waitlistSchema>;

export const isEmail = (s: string) => /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(s);
