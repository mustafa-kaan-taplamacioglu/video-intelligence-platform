import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Layout from './components/Layout';
import HomePage from './pages/HomePage';
import VideoPage from './pages/VideoPage';
import ClipPage from './pages/ClipPage';
import DetectionPage from './pages/DetectionPage';
import LiveStreamPage from './pages/LiveStreamPage';

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route element={<Layout />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/video/:id" element={<VideoPage />} />
          <Route path="/clip/:id" element={<ClipPage />} />
          <Route path="/detection" element={<DetectionPage />} />
          <Route path="/livestream" element={<LiveStreamPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
