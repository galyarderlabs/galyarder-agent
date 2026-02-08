/**
 * WhatsApp client wrapper using Baileys.
 * Based on OpenClaw's working implementation.
 */

/* eslint-disable @typescript-eslint/no-explicit-any */
import makeWASocket, {
  DisconnectReason,
  useMultiFileAuthState,
  fetchLatestBaileysVersion,
  makeCacheableSignalKeyStore,
  downloadMediaMessage,
} from '@whiskeysockets/baileys';

import { Boom } from '@hapi/boom';
import qrcode from 'qrcode-terminal';
import pino from 'pino';
import { mkdirSync, writeFileSync } from 'fs';
import { basename, join } from 'path';

const VERSION = '0.1.0';

export interface InboundMessage {
  id: string;
  sender: string;
  chatId: string;
  content: string;
  timestamp: number;
  isGroup: boolean;
  fromMe?: boolean;
  mediaType?: string;
  mimeType?: string;
  mediaPath?: string;
  caption?: string;
}

export interface WhatsAppClientOptions {
  authDir: string;
  onMessage: (msg: InboundMessage) => void;
  onQR: (qr: string) => void;
  onStatus: (status: string) => void;
}

interface SendOptions {
  mediaPath?: string;
  mediaType?: string;
  mimeType?: string;
  caption?: string;
}

export class WhatsAppClient {
  private sock: any = null;
  private options: WhatsAppClientOptions;
  private reconnecting = false;
  private recentOutgoing: Array<{ to: string; text: string; id?: string; at: number }> = [];
  private readonly outgoingWindowMs = 30000;
  private readonly mediaDir: string;

  constructor(options: WhatsAppClientOptions) {
    this.options = options;
    this.mediaDir = join(this.options.authDir, '..', 'media-cache');
    mkdirSync(this.mediaDir, { recursive: true });
  }

  async connect(): Promise<void> {
    const logger = pino({ level: 'silent' });
    const { state, saveCreds } = await useMultiFileAuthState(this.options.authDir);
    const { version } = await fetchLatestBaileysVersion();

    console.log(`Using Baileys version: ${version.join('.')}`);

    this.sock = makeWASocket({
      auth: {
        creds: state.creds,
        keys: makeCacheableSignalKeyStore(state.keys, logger),
      },
      version,
      logger,
      printQRInTerminal: false,
      browser: ['g-agent', 'cli', VERSION],
      syncFullHistory: false,
      markOnlineOnConnect: false,
    });

    if (this.sock.ws && typeof this.sock.ws.on === 'function') {
      this.sock.ws.on('error', (err: Error) => {
        console.error('WebSocket error:', err.message);
      });
    }

    this.sock.ev.on('connection.update', async (update: any) => {
      const { connection, lastDisconnect, qr } = update;

      if (qr) {
        console.log('\n📱 Scan this QR code with WhatsApp (Linked Devices):\n');
        qrcode.generate(qr, { small: true });
        this.options.onQR(qr);
      }

      if (connection === 'close') {
        const statusCode = (lastDisconnect?.error as Boom)?.output?.statusCode;
        const shouldReconnect = statusCode !== DisconnectReason.loggedOut;

        console.log(`Connection closed. Status: ${statusCode}, Will reconnect: ${shouldReconnect}`);
        this.options.onStatus('disconnected');

        if (shouldReconnect && !this.reconnecting) {
          this.reconnecting = true;
          console.log('Reconnecting in 5 seconds...');
          setTimeout(() => {
            this.reconnecting = false;
            this.connect();
          }, 5000);
        }
      } else if (connection === 'open') {
        console.log('✅ Connected to WhatsApp');
        this.options.onStatus('connected');
      }
    });

    this.sock.ev.on('creds.update', saveCreds);

    this.sock.ev.on('messages.upsert', async ({ messages, type }: { messages: any[]; type: string }) => {
      if (type !== 'notify') return;

      for (const msg of messages) {
        const remoteJid = msg.key?.remoteJid || '';
        if (!remoteJid || remoteJid === 'status@broadcast') continue;

        const payload = this.extractMessagePayload(msg);
        if (!payload.content) continue;

        if (this.isOutgoingEcho(msg, payload.content)) continue;

        const isGroup = remoteJid.endsWith('@g.us');
        let mediaPath: string | undefined;
        if (payload.mediaType && ['image', 'video', 'audio', 'voice', 'document', 'sticker'].includes(payload.mediaType)) {
          mediaPath = await this.downloadMediaToFile(msg, payload.mediaType, payload.mimeType);
        }

        this.options.onMessage({
          id: msg.key?.id || '',
          sender: this.resolveSenderJid(msg),
          chatId: remoteJid,
          content: payload.content,
          timestamp: Number(msg.messageTimestamp || 0),
          isGroup,
          fromMe: Boolean(msg.key?.fromMe),
          mediaType: payload.mediaType,
          mimeType: payload.mimeType,
          mediaPath,
          caption: payload.caption,
        });
      }
    });
  }

  private extractMessagePayload(
    msg: any
  ): { content: string | null; mediaType?: string; mimeType?: string; caption?: string } {
    const message = msg.message;
    if (!message) return { content: null };

    if (message.conversation) {
      return { content: message.conversation };
    }

    if (message.extendedTextMessage?.text) {
      return { content: message.extendedTextMessage.text };
    }

    if (message.imageMessage) {
      const caption = message.imageMessage.caption ? ` ${message.imageMessage.caption}` : '';
      return {
        content: `[Image]${caption}`,
        mediaType: 'image',
        mimeType: message.imageMessage.mimetype,
        caption: message.imageMessage.caption,
      };
    }

    if (message.videoMessage) {
      const caption = message.videoMessage.caption ? ` ${message.videoMessage.caption}` : '';
      return {
        content: `[Video]${caption}`,
        mediaType: 'video',
        mimeType: message.videoMessage.mimetype,
        caption: message.videoMessage.caption,
      };
    }

    if (message.documentMessage) {
      const name = message.documentMessage.fileName || 'document';
      const caption = message.documentMessage.caption ? ` ${message.documentMessage.caption}` : '';
      return {
        content: `[Document:${name}]${caption}`,
        mediaType: 'document',
        mimeType: message.documentMessage.mimetype,
        caption: message.documentMessage.caption,
      };
    }

    if (message.stickerMessage) {
      return {
        content: '[Sticker]',
        mediaType: 'sticker',
        mimeType: message.stickerMessage.mimetype || 'image/webp',
      };
    }

    if (message.audioMessage) {
      const isPtt = Boolean(message.audioMessage.ptt);
      return {
        content: isPtt ? '[Voice Message]' : '[Audio Message]',
        mediaType: isPtt ? 'voice' : 'audio',
        mimeType: message.audioMessage.mimetype,
      };
    }

    return { content: null };
  }

  async sendMessage(to: string, text: string, options: SendOptions = {}): Promise<void> {
    if (!this.sock) {
      throw new Error('Not connected');
    }

    const mediaPath = (options.mediaPath || '').trim();
    const mediaType = this.resolveOutboundMediaType(mediaPath, options.mediaType);
    const caption = (options.caption || text || '').trim();
    let payload: Record<string, unknown>;

    if (mediaPath) {
      if (mediaType === 'image') {
        payload = {
          image: { url: mediaPath },
          caption,
          mimetype: options.mimeType || undefined,
        };
      } else if (mediaType === 'voice') {
        payload = {
          audio: { url: mediaPath },
          ptt: true,
          mimetype: options.mimeType || 'audio/ogg; codecs=opus',
        };
      } else if (mediaType === 'audio') {
        payload = {
          audio: { url: mediaPath },
          ptt: false,
          mimetype: options.mimeType || undefined,
        };
      } else if (mediaType === 'sticker') {
        payload = {
          sticker: { url: mediaPath },
        };
      } else {
        payload = {
          document: { url: mediaPath },
          fileName: basename(mediaPath),
          caption,
          mimetype: options.mimeType || undefined,
        };
      }
    } else {
      payload = { text };
    }

    const sent = await this.sock.sendMessage(to, payload);
    const sentId = sent?.key?.id as string | undefined;
    this.trackOutgoing(to, text, sentId);
  }

  async disconnect(): Promise<void> {
    if (this.sock) {
      this.sock.end(undefined);
      this.sock = null;
    }
  }

  private trackOutgoing(to: string, text: string, id?: string): void {
    const now = Date.now();
    this.recentOutgoing.push({ to, text, id, at: now });
    this.recentOutgoing = this.recentOutgoing.filter((entry) => now - entry.at <= this.outgoingWindowMs);
  }

  private isOutgoingEcho(msg: any, content: string): boolean {
    if (!msg.key?.fromMe) return false;

    const now = Date.now();
    const remoteJid = msg.key.remoteJid || '';
    const messageId = msg.key.id as string | undefined;
    this.recentOutgoing = this.recentOutgoing.filter((entry) => now - entry.at <= this.outgoingWindowMs);

    return this.recentOutgoing.some((entry) => (
      entry.to === remoteJid &&
      (Boolean(messageId && entry.id === messageId) || entry.text === content)
    ));
  }

  private resolveSenderJid(msg: any): string {
    const key = msg.key || {};
    return key.participant || key.senderPn || key.remoteJid || '';
  }

  private extensionForMedia(mediaType: string, mimeType?: string): string {
    if (mimeType && mimeType.includes('/')) {
      const ext = mimeType.split('/')[1].split(';')[0].trim();
      if (ext) return ext;
    }
    if (mediaType === 'image') return 'jpg';
    if (mediaType === 'video') return 'mp4';
    if (mediaType === 'voice') return 'ogg';
    if (mediaType === 'audio') return 'mp3';
    if (mediaType === 'document') return 'bin';
    if (mediaType === 'sticker') return 'webp';
    return 'dat';
  }

  private resolveOutboundMediaType(mediaPath: string, explicitType?: string): string {
    const normalized = (explicitType || '').trim().toLowerCase();
    if (['image', 'voice', 'audio', 'document', 'sticker'].includes(normalized)) {
      return normalized;
    }
    const suffix = mediaPath.toLowerCase();
    if (suffix.endsWith('.webp') || suffix.endsWith('.tgs')) return 'sticker';
    if (suffix.endsWith('.jpg') || suffix.endsWith('.jpeg') || suffix.endsWith('.png') || suffix.endsWith('.gif')) return 'image';
    if (suffix.endsWith('.ogg') || suffix.endsWith('.opus')) return 'voice';
    if (suffix.endsWith('.mp3') || suffix.endsWith('.wav') || suffix.endsWith('.m4a') || suffix.endsWith('.flac')) return 'audio';
    return 'document';
  }

  private async downloadMediaToFile(msg: any, mediaType: string, mimeType?: string): Promise<string | undefined> {
    if (!this.sock) return undefined;
    try {
      const logger = pino({ level: 'silent' });
      const buffer = await downloadMediaMessage(
        msg,
        'buffer',
        {},
        { logger, reuploadRequest: this.sock.updateMediaMessage }
      ) as unknown;
      if (!(buffer instanceof Uint8Array) || buffer.byteLength === 0) return undefined;

      const ext = this.extensionForMedia(mediaType, mimeType);
      const msgId = (msg.key?.id || `msg-${Date.now()}`).replace(/[^a-zA-Z0-9_-]/g, '');
      const filePath = join(this.mediaDir, `${Date.now()}-${msgId}.${ext}`);
      writeFileSync(filePath, buffer);
      return filePath;
    } catch (error) {
      console.warn('Failed to download WhatsApp media:', String(error));
      return undefined;
    }
  }
}
