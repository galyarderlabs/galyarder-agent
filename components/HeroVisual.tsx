'use client';

import { useEffect, useRef } from 'react';
import { motion } from 'framer-motion';

export function HeroVisual() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;

    const ctx = canvas.getContext('2d');
    if (!ctx) return;

    // Set canvas size
    const resizeCanvas = () => {
      canvas.width = canvas.offsetWidth * window.devicePixelRatio;
      canvas.height = canvas.offsetHeight * window.devicePixelRatio;
      ctx.scale(window.devicePixelRatio, window.devicePixelRatio);
    };
    resizeCanvas();
    window.addEventListener('resize', resizeCanvas);

    // Particle system for network visualization
    const particles: Array<{
      x: number;
      y: number;
      vx: number;
      vy: number;
      radius: number;
      connected: number[];
      pulsePhase: number;
      type: 'node' | 'execution' | 'protocol';
    }> = [];

    const numParticles = 50;
    const connectionDistance = 150;

    // Initialize particles
    for (let i = 0; i < numParticles; i++) {
      const types: Array<'node' | 'execution' | 'protocol'> = ['node', 'execution', 'protocol'];
      particles.push({
        x: Math.random() * canvas.offsetWidth,
        y: Math.random() * canvas.offsetHeight,
        vx: (Math.random() - 0.5) * 0.3,
        vy: (Math.random() - 0.5) * 0.3,
        radius: Math.random() * 2 + 1,
        connected: [],
        pulsePhase: Math.random() * Math.PI * 2,
        type: types[Math.floor(Math.random() * types.length)]!,
      });
    }

    let animationId: number;
    let mouseX = 0;
    let mouseY = 0;

    const handleMouseMove = (e: MouseEvent) => {
      const rect = canvas.getBoundingClientRect();
      mouseX = e.clientX - rect.left;
      mouseY = e.clientY - rect.top;
    };
    canvas.addEventListener('mousemove', handleMouseMove);

    const animate = () => {
      ctx.fillStyle = 'rgba(11, 15, 20, 0.05)';
      ctx.fillRect(0, 0, canvas.offsetWidth, canvas.offsetHeight);

      particles.forEach((particle, i) => {
        // Update position
        particle.x += particle.vx;
        particle.y += particle.vy;
        particle.pulsePhase += 0.02;

        // Bounce off walls
        if (particle.x < 0 || particle.x > canvas.offsetWidth) particle.vx *= -1;
        if (particle.y < 0 || particle.y > canvas.offsetHeight) particle.vy *= -1;

        // Mouse interaction
        const dx = mouseX - particle.x;
        const dy = mouseY - particle.y;
        const distance = Math.sqrt(dx * dx + dy * dy);
        if (distance < 100) {
          particle.vx += dx * 0.00001;
          particle.vy += dy * 0.00001;
        }

        // Draw connections
        particle.connected = [];
        particles.forEach((otherParticle, j) => {
          if (i !== j) {
            const dx = particle.x - otherParticle.x;
            const dy = particle.y - otherParticle.y;
            const distance = Math.sqrt(dx * dx + dy * dy);

            if (distance < connectionDistance) {
              particle.connected.push(j);
              const opacity = (1 - distance / connectionDistance) * 0.3;
              
              // Draw connection line
              ctx.beginPath();
              ctx.moveTo(particle.x, particle.y);
              ctx.lineTo(otherParticle.x, otherParticle.y);
              
              // Color based on particle types
              if (particle.type === 'execution' || otherParticle.type === 'execution') {
                ctx.strokeStyle = `rgba(190, 30, 45, ${opacity})`;
              } else if (particle.type === 'protocol' || otherParticle.type === 'protocol') {
                ctx.strokeStyle = `rgba(59, 130, 246, ${opacity})`;
              } else {
                ctx.strokeStyle = `rgba(148, 163, 184, ${opacity})`;
              }
              
              ctx.lineWidth = 0.5;
              ctx.stroke();
            }
          }
        });

        // Draw particle
        const pulseSize = Math.sin(particle.pulsePhase) * 0.5 + 1;
        ctx.beginPath();
        ctx.arc(particle.x, particle.y, particle.radius * pulseSize, 0, Math.PI * 2);
        
        // Particle color based on type
        if (particle.type === 'execution') {
          ctx.fillStyle = 'rgba(190, 30, 45, 0.8)';
          ctx.shadowBlur = 10;
          ctx.shadowColor = 'rgba(190, 30, 45, 0.5)';
        } else if (particle.type === 'protocol') {
          ctx.fillStyle = 'rgba(59, 130, 246, 0.8)';
          ctx.shadowBlur = 10;
          ctx.shadowColor = 'rgba(59, 130, 246, 0.5)';
        } else {
          ctx.fillStyle = 'rgba(148, 163, 184, 0.6)';
          ctx.shadowBlur = 5;
          ctx.shadowColor = 'rgba(148, 163, 184, 0.3)';
        }
        
        ctx.fill();
        ctx.shadowBlur = 0;
      });

      animationId = requestAnimationFrame(animate);
    };

    animate();

    return () => {
      cancelAnimationFrame(animationId);
      window.removeEventListener('resize', resizeCanvas);
      canvas.removeEventListener('mousemove', handleMouseMove);
    };
  }, []);

  return (
    <div className="absolute inset-0 overflow-hidden">
      <canvas
        ref={canvasRef}
        className="absolute inset-0 w-full h-full opacity-60"
        style={{ background: 'transparent' }}
      />
      
      {/* Floating protocol badges */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 0.5 }}
        className="absolute top-20 left-10 hidden lg:block"
      >
        <div className="glass px-3 py-2 rounded-lg border border-blue-500/30">
          <code className="text-xs text-blue-400">protocol.execute()</code>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 0.7 }}
        className="absolute top-40 right-20 hidden lg:block"
      >
        <div className="glass px-3 py-2 rounded-lg border border-green-500/30">
          <code className="text-xs text-green-400">memory.checkpoint()</code>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 0.9 }}
        className="absolute bottom-40 left-1/4 hidden lg:block"
      >
        <div className="glass px-3 py-2 rounded-lg border border-purple-500/30">
          <code className="text-xs text-purple-400">agent.plan()</code>
        </div>
      </motion.div>

      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 1, delay: 1.1 }}
        className="absolute bottom-20 right-1/3 hidden lg:block"
      >
        <div className="glass px-3 py-2 rounded-lg border border-accent-red/30">
          <code className="text-xs text-accent-red">action.sign()</code>
        </div>
      </motion.div>

      {/* Animated gradient orbs */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-blue-500/10 rounded-full filter blur-3xl animate-pulse" />
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-purple-500/10 rounded-full filter blur-3xl animate-pulse animation-delay-2000" />
      <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-96 h-96 bg-accent-red/5 rounded-full filter blur-3xl animate-pulse animation-delay-4000" />
    </div>
  );
}
