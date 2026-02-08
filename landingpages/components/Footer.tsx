import { copy } from '@/lib/copy';

export function Footer() {
  return (
    <footer className="border-t border-slate-800 bg-black/50 backdrop-blur-sm">
      <div className="container-section py-12">
        <div className="flex flex-col md:flex-row justify-between items-center gap-6">
          <div className="flex flex-col items-center md:items-start gap-2">
            <p className="text-sm text-slate-400">{copy.footer.note}</p>
            <p className="text-xs text-slate-500">{copy.footer.copyright}</p>
          </div>
          
          <nav className="flex items-center gap-6">
            <a
              href={copy.footer.links.docs}
              className="text-sm text-slate-400 hover:text-slate-100 transition-colors"
            >
              Docs
            </a>
            <a
              href={copy.footer.links.blog}
              className="text-sm text-slate-400 hover:text-slate-100 transition-colors"
            >
              Blog
            </a>
            <a
              href={copy.footer.links.contact}
              className="text-sm text-slate-400 hover:text-slate-100 transition-colors"
            >
              Contact
            </a>
          </nav>
        </div>
      </div>
    </footer>
  );
}
