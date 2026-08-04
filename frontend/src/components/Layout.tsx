import { Link, Outlet } from 'react-router-dom';

export default function Layout() {
  return (
    <div className="flex flex-col min-h-screen">
      <header className="border-b border-gray-800 bg-panel">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <Link to="/" className="flex items-center gap-3 no-underline">
            <div className="w-8 h-8 bg-accent rounded flex items-center justify-center">
              <svg viewBox="0 0 24 24" className="w-5 h-5 text-white" fill="currentColor">
                <path d="M8 5v14l11-7z" />
              </svg>
            </div>
            <div>
              <span className="text-white font-bold tracking-widest text-sm">VIDEO INTELLIGENCE</span>
              <span className="text-muted text-xs ml-2 hidden sm:inline">Real-Time Activity Detection Platform</span>
            </div>
          </Link>
          <nav className="flex gap-4 text-sm">
            <Link to="/" className="text-gray-400 hover:text-white transition-colors no-underline">
              Videos
            </Link>
            <Link to="/detection" className="text-gray-400 hover:text-white transition-colors no-underline">
              AI Analysis
            </Link>
            <Link to="/livestream" className="text-gray-400 hover:text-white transition-colors no-underline">
              Live Stream
            </Link>
          </nav>
        </div>
      </header>

      <main className="flex-1 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
        <Outlet />
      </main>

      <footer className="border-t border-gray-800 py-4 text-center text-xs text-muted">
        Video Intelligence Platform — MediaPipe Pose + BiLSTM activity detection
      </footer>
    </div>
  );
}
