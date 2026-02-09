import { NextRequest, NextResponse } from 'next/server';
import { waitlistSchema } from '@/lib/schema';
import { z } from 'zod';
import { kv } from '@vercel/kv';
import { Ratelimit } from '@upstash/ratelimit';
import { createHash, timingSafeEqual } from 'crypto';

// Create a rate limiter: 10 requests per 1 minute per IP
const ratelimit = new Ratelimit({
  redis: kv,
  limiter: Ratelimit.slidingWindow(10, '1 m'),
  analytics: true,
  prefix: '@upstash/ratelimit/agent',
});

interface WaitlistEntry {
  email: string;
  role?: 'Builder' | 'Operator' | 'Researcher';
  consent: boolean;
  timestamp: string;
  userAgent: string;
  ipHash?: string;
}

const _missingStatsToken = '__missing_stats_token__';

const normalizeIp = (rawValue: string | null): string => {
  if (!rawValue) {
    return 'unknown';
  }
  const first = rawValue.split(',')[0]?.trim();
  return first || 'unknown';
};

const hashIp = (ip: string): string | undefined => {
  if (ip === 'unknown') {
    return undefined;
  }
  const salt = process.env.WAITLIST_IP_SALT?.trim();
  if (!salt) {
    return undefined;
  }
  return createHash('sha256').update(`${salt}:${ip}`).digest('hex');
};

const getStatsToken = (): string => process.env.WAITLIST_STATS_TOKEN?.trim() || _missingStatsToken;

const tokenMatches = (expected: string, provided: string): boolean => {
  const expectedBuffer = Buffer.from(expected);
  const providedBuffer = Buffer.from(provided);
  if (expectedBuffer.length !== providedBuffer.length) {
    return false;
  }
  return timingSafeEqual(expectedBuffer, providedBuffer);
};

export async function POST(request: NextRequest) {
  try {
    // Get IP for rate limiting
    const ip = normalizeIp(request.headers.get('x-forwarded-for') || request.headers.get('x-real-ip'));

    // Check rate limit
    const { success, limit, remaining, reset } = await ratelimit.limit(ip);

    if (!success) {
      return NextResponse.json(
        { error: 'Too many requests. Please try again later.' },
        {
          status: 429,
          headers: {
            'X-RateLimit-Limit': limit.toString(),
            'X-RateLimit-Remaining': remaining.toString(),
            'X-RateLimit-Reset': reset.toString(),
          },
        },
      );
    }

    const body = await request.json();

    // Validate the input
    const validatedData = waitlistSchema.parse(body);

    // Check for honeypot field (anti-spam)
    if (validatedData.honeypot) {
      return NextResponse.json({ ok: true });
    }

    // Check if email already exists in KV
    const existingEntry = await kv.get(`waitlist:email:${validatedData.email}`);

    if (existingEntry) {
      return NextResponse.json({ error: 'This email is already on the waitlist' }, { status: 400 });
    }

    // Create new entry
    const newEntry: WaitlistEntry = {
      email: validatedData.email,
      role: validatedData.role,
      consent: validatedData.consent,
      timestamp: new Date().toISOString(),
      userAgent: request.headers.get('user-agent') || 'unknown',
      ipHash: hashIp(ip),
    };

    // Store in KV with email as key
    await kv.set(`waitlist:email:${validatedData.email}`, newEntry);

    // Add to sorted set for chronological listing
    await kv.zadd('waitlist:chronological', {
      score: Date.now(),
      member: validatedData.email,
    });

    // Increment total count
    await kv.incr('waitlist:total');

    // Increment role count if provided
    if (validatedData.role) {
      await kv.hincrby('waitlist:roles', validatedData.role, 1);
    } else {
      await kv.hincrby('waitlist:roles', 'unspecified', 1);
    }

    // Log for monitoring
    console.log(
      `[WAITLIST] New signup: ${validatedData.email} (${validatedData.role || 'no role'})`,
    );

    return NextResponse.json(
      { ok: true },
      {
        headers: {
          'X-RateLimit-Limit': limit.toString(),
          'X-RateLimit-Remaining': remaining.toString(),
          'X-RateLimit-Reset': reset.toString(),
        },
      },
    );
  } catch (error) {
    console.error('[WAITLIST] Error:', error);

    if (error instanceof z.ZodError) {
      return NextResponse.json(
        { error: 'Invalid data provided', details: error.issues },
        { status: 400 },
      );
    }

    return NextResponse.json({ error: 'Something went wrong. Please try again.' }, { status: 500 });
  }
}

export async function GET(request: NextRequest) {
  const statsToken = getStatsToken();
  if (statsToken === _missingStatsToken) {
    return NextResponse.json({ error: 'Not found' }, { status: 404 });
  }

  const providedToken =
    request.headers.get('x-waitlist-stats-token')?.trim() ||
    request.nextUrl.searchParams.get('token')?.trim() ||
    '';
  if (!tokenMatches(statsToken, providedToken)) {
    return NextResponse.json({ error: 'Forbidden' }, { status: 403 });
  }

  try {
    const total = (await kv.get<number>('waitlist:total')) || 0;
    const roles = (await kv.hgetall<Record<string, number>>('waitlist:roles')) || {};

    // Get last 5 signups (just timestamps for privacy)
    const recentEmails = await kv.zrange('waitlist:chronological', -5, -1);
    let lastSignup = null;

    if (recentEmails && recentEmails.length > 0) {
      const lastEmail = recentEmails[recentEmails.length - 1];
      const lastEntry = await kv.get<WaitlistEntry>(`waitlist:email:${lastEmail}`);
      lastSignup = lastEntry?.timestamp || null;
    }

    return NextResponse.json({
      total,
      roles,
      lastSignup,
    });
  } catch (error) {
    console.error('[WAITLIST] Stats error:', error);
    return NextResponse.json({ error: 'Failed to fetch stats' }, { status: 500 });
  }
}
