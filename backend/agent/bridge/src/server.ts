/**
 * WebSocket server for Python-Node.js bridge communication.
 */

import { WebSocketServer, WebSocket } from 'ws';
import { WhatsAppClient } from './whatsapp.js';

interface SendCommand {
  type: 'send';
  to: string;
  text: string;
  mediaPath?: string;
  mediaType?: string;
  mimeType?: string;
  caption?: string;
  request_id?: string;
}

interface ActionCommand {
  type: 'action';
  to: string;
  action: string;
  request_id?: string;
}

type Command = SendCommand | ActionCommand;

interface AuthMessage {
  type: 'auth';
  token: string;
}

interface BridgeMessage {
  type: 'message' | 'status' | 'qr' | 'error';
  [key: string]: unknown;
}

export class BridgeServer {
  private wss: WebSocketServer | null = null;
  private wa: WhatsAppClient | null = null;
  private clients: Set<WebSocket> = new Set();

  constructor(
    private host: string,
    private port: number,
    private authDir: string,
    private token: string = '',
  ) {}

  async start(): Promise<void> {
    const wss = new WebSocketServer({ host: this.host, port: this.port });
    this.wss = wss;

    await new Promise<void>((resolve, reject) => {
      const onListening = () => {
        wss.off('error', onError);
        resolve();
      };
      const onError = (error: Error) => {
        wss.off('listening', onListening);
        this.wss = null;
        reject(error);
      };

      wss.once('listening', onListening);
      wss.once('error', onError);
    });
    console.log(`🌉 Bridge server listening on ws://${this.host}:${this.port}`);

    wss.on('error', (error) => {
      const message = error instanceof Error ? error.message : String(error);
      console.error(`Bridge server error: ${message}`);
    });

    // Initialize WhatsApp client
    this.wa = new WhatsAppClient({
      authDir: this.authDir,
      onMessage: (msg) => this.broadcast({ type: 'message', ...msg }),
      onQR: (qr) => this.broadcast({ type: 'qr', qr }),
      onStatus: (status) => this.broadcast({ type: 'status', status }),
    });

    // Handle WebSocket connections
    wss.on('connection', (ws) => {
      console.log('🔗 Python client connected');

      if (this.token) {
        // Wait for auth message within 5 seconds
        const authTimeout = setTimeout(() => {
          console.log('⛔ Auth timeout, closing connection');
          ws.close(4003, 'Auth timeout');
        }, 5000);

        ws.once('message', (data) => {
          clearTimeout(authTimeout);
          try {
            const msg = JSON.parse(data.toString()) as AuthMessage;
            if (msg.type === 'auth' && msg.token === this.token) {
              console.log('🔓 Client authenticated');
              this.acceptClient(ws);
            } else {
              console.log('⛔ Invalid auth token');
              ws.close(4003, 'Invalid token');
            }
          } catch {
            console.log('⛔ Invalid auth message');
            ws.close(4003, 'Invalid auth message');
          }
        });
      } else {
        this.acceptClient(ws);
      }
    });

    // Connect to WhatsApp
    await this.wa.connect();
  }

  private acceptClient(ws: WebSocket): void {
    this.clients.add(ws);

    ws.on('message', async (data) => {
      try {
        const cmd = JSON.parse(data.toString()) as Command;
        await this.handleCommand(cmd);
        const ack = { type: 'sent' as const, to: cmd.to, request_id: cmd.request_id ?? null };
        ws.send(JSON.stringify(ack));
      } catch (error) {
        console.error('Error handling command:', error);
        let requestId: string | undefined;
        try {
          const parsed = JSON.parse(data.toString()) as Partial<SendCommand>;
          requestId = parsed.request_id;
        } catch {
          requestId = undefined;
        }
        ws.send(
          JSON.stringify({
            type: 'error',
            error: error instanceof Error ? error.message : String(error),
            category: 'send_error',
            request_id: requestId,
          })
        );
      }
    });

    ws.on('close', () => {
      console.log('🔌 Python client disconnected');
      this.clients.delete(ws);
    });

    ws.on('error', (error) => {
      console.error('WebSocket error:', error);
      this.clients.delete(ws);
    });
  }

  private async handleCommand(cmd: Command): Promise<void> {
    if (this.wa) {
      if (cmd.type === 'send') {
        await this.wa.sendMessage(cmd.to, cmd.text, {
          mediaPath: cmd.mediaPath,
          mediaType: cmd.mediaType,
          mimeType: cmd.mimeType,
          caption: cmd.caption,
        });
      } else if (cmd.type === 'action') {
        await this.wa.sendAction(cmd.to, cmd.action);
      }
    }
  }

  private broadcast(msg: BridgeMessage): void {
    const data = JSON.stringify(msg);
    for (const client of this.clients) {
      if (client.readyState === WebSocket.OPEN) {
        client.send(data);
      }
    }
  }

  async stop(): Promise<void> {
    // Close all client connections
    for (const client of this.clients) {
      client.close();
    }
    this.clients.clear();

    // Close WebSocket server
    if (this.wss) {
      this.wss.close();
      this.wss = null;
    }

    // Disconnect WhatsApp
    if (this.wa) {
      await this.wa.disconnect();
      this.wa = null;
    }
  }
}
