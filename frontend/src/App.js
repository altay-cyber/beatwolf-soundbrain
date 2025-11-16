import { useState, useRef, useEffect } from "react";
import "@/App.css";
import { BrowserRouter, Routes, Route } from "react-router-dom";
import axios from "axios";
import { Mic, Square, Music, Heart, Clock, Sparkles, Play, ExternalLink, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toast } from "sonner";

const BACKEND_URL = process.env.REACT_APP_BACKEND_URL;
const API = `${BACKEND_URL}/api`;

const Home = () => {
  const [isRecording, setIsRecording] = useState(false);
  const [isIdentifying, setIsIdentifying] = useState(false);
  const [identifiedSong, setIdentifiedSong] = useState(null);
  const [history, setHistory] = useState([]);
  const [favorites, setFavorites] = useState([]);
  const [activeTab, setActiveTab] = useState("identify");
  const [audioLevel, setAudioLevel] = useState(0);
  
  const mediaRecorderRef = useRef(null);
  const audioChunksRef = useRef([]);
  const audioContextRef = useRef(null);
  const analyserRef = useRef(null);
  const animationFrameRef = useRef(null);

  // Türkçe dil desteği
  const tr = {
    appName: "BeatWolf",
    subtitle: "Saniyeler içinde herhangi bir şarkıyı keşfedin",
    identify: "Tanımla",
    history: "Geçmiş",
    favorites: "Favoriler",
    startRecording: "Kayda Başla",
    stopRecording: "Kaydı Durdur",
    identifying: "Tanımlanıyor...",
    identifiedSong: "Tanımlanan Şarkı",
    recentIdentifications: "Son Tanımlamalar",
    yourFavorites: "Favorileriniz",
    noHistoryYet: "Henüz geçmiş yok",
    startIdentifying: "Şarkıları tanımlamaya başlayın",
    noFavoritesYet: "Henüz favori yok",
    addFavorites: "Şarkıları favorilerinize ekleyin",
    addToFavorites: "Favorilere Ekle",
    delete: "Sil",
    released: "Yayınlandı",
    recordingStarted: "Kayıt başladı! 5-10 saniye ses kaydedin",
    couldNotAccessMic: "Mikrofona erişilemedi",
    found: "Bulundu",
    by: "sanatçısı",
    addedToFavorites: "Favorilere eklendi!",
    couldNotAddToFavorites: "Favorilere eklenemedi",
    removedFromFavorites: "Favorilerden kaldırıldı",
    couldNotRemoveFromFavorites: "Favorilerden kaldırılamadı",
    deletedFromHistory: "Geçmişten silindi",
    couldNotDeleteFromHistory: "Geçmişten silinemedi",
    couldNotIdentify: "Şarkı tanımlanamadı",
    copyright: "© 2025 BeatWolf. Tüm hakları saklıdır.",
    poweredBy: "Powered by AudD API"
  };

  useEffect(() => {
    fetchHistory();
    fetchFavorites();
  }, []);

  const fetchHistory = async () => {
    try {
      const response = await axios.get(`${API}/history`);
      setHistory(response.data);
    } catch (error) {
      console.error("Error fetching history:", error);
    }
  };

  const fetchFavorites = async () => {
    try {
      const response = await axios.get(`${API}/favorites`);
      setFavorites(response.data);
    } catch (error) {
      console.error("Error fetching favorites:", error);
    }
  };

  const visualizeAudio = (stream) => {
    audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
    analyserRef.current = audioContextRef.current.createAnalyser();
    const source = audioContextRef.current.createMediaStreamSource(stream);
    source.connect(analyserRef.current);
    analyserRef.current.fftSize = 256;
    
    const bufferLength = analyserRef.current.frequencyBinCount;
    const dataArray = new Uint8Array(bufferLength);
    
    const updateLevel = () => {
      analyserRef.current.getByteFrequencyData(dataArray);
      const average = dataArray.reduce((a, b) => a + b) / bufferLength;
      setAudioLevel(average / 255);
      animationFrameRef.current = requestAnimationFrame(updateLevel);
    };
    
    updateLevel();
  };

  const startRecording = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorderRef.current = new MediaRecorder(stream);
      audioChunksRef.current = [];

      visualizeAudio(stream);

      mediaRecorderRef.current.ondataavailable = (event) => {
        audioChunksRef.current.push(event.data);
      };

      mediaRecorderRef.current.onstop = async () => {
        const audioBlob = new Blob(audioChunksRef.current, { type: "audio/wav" });
        await identifySong(audioBlob);
        
        // Stop visualization
        if (animationFrameRef.current) {
          cancelAnimationFrame(animationFrameRef.current);
        }
        if (audioContextRef.current) {
          audioContextRef.current.close();
        }
        setAudioLevel(0);
        
        // Stop all tracks
        stream.getTracks().forEach(track => track.stop());
      };

      mediaRecorderRef.current.start();
      setIsRecording(true);
      toast.success(tr.recordingStarted);
    } catch (error) {
      console.error("Error accessing microphone:", error);
      toast.error(tr.couldNotAccessMic);
    }
  };

  const stopRecording = () => {
    if (mediaRecorderRef.current && isRecording) {
      mediaRecorderRef.current.stop();
      setIsRecording(false);
    }
  };

  const identifySong = async (audioBlob) => {
    setIsIdentifying(true);
    try {
      const formData = new FormData();
      formData.append("file", audioBlob, "recording.wav");

      const response = await axios.post(`${API}/identify`, formData, {
        headers: { "Content-Type": "multipart/form-data" },
      });

      setIdentifiedSong(response.data);
      toast.success(`${tr.found}: ${response.data.title} ${tr.by} ${response.data.artist}`);
      fetchHistory();
    } catch (error) {
      console.error("Error identifying song:", error);
      toast.error(error.response?.data?.detail || tr.couldNotIdentify);
    } finally {
      setIsIdentifying(false);
    }
  };

  const addToFavorites = async (song) => {
    try {
      await axios.post(`${API}/favorites`, {
        title: song.title,
        artist: song.artist,
        album: song.album,
        release_date: song.release_date,
        artwork: song.artwork,
        preview_url: song.preview_url,
        spotify_url: song.spotify_url,
        apple_music_url: song.apple_music_url,
      });
      toast.success("Added to favorites!");
      fetchFavorites();
    } catch (error) {
      toast.error(error.response?.data?.detail || "Could not add to favorites");
    }
  };

  const removeFromFavorites = async (id) => {
    try {
      await axios.delete(`${API}/favorites/${id}`);
      toast.success("Removed from favorites");
      fetchFavorites();
    } catch (error) {
      toast.error("Could not remove from favorites");
    }
  };

  const deleteHistoryItem = async (id) => {
    try {
      await axios.delete(`${API}/history/${id}`);
      toast.success("Deleted from history");
      fetchHistory();
    } catch (error) {
      toast.error("Could not delete from history");
    }
  };

  const SongCard = ({ song, showFavoriteButton = true, showDeleteButton = false, onDelete }) => (
    <Card className="song-card" data-testid="song-card">
      <CardContent className="p-0">
        <div className="flex gap-4 p-4">
          {song.artwork ? (
            <img
              src={song.artwork}
              alt={song.title}
              className="w-24 h-24 rounded-lg object-cover flex-shrink-0"
              data-testid="song-artwork"
            />
          ) : (
            <div className="w-24 h-24 rounded-lg bg-gradient-to-br from-orange-400 to-pink-500 flex items-center justify-center flex-shrink-0">
              <Music className="w-12 h-12 text-white" />
            </div>
          )}
          <div className="flex-1 min-w-0">
            <h3 className="text-lg font-bold text-white truncate" data-testid="song-title">{song.title}</h3>
            <p className="text-gray-300 truncate" data-testid="song-artist">{song.artist}</p>
            {song.album && <p className="text-sm text-gray-400 truncate" data-testid="song-album">{song.album}</p>}
            {song.release_date && <p className="text-xs text-gray-500 mt-1" data-testid="song-release-date">Released: {song.release_date}</p>}
            
            <div className="flex gap-2 mt-3 flex-wrap">
              {song.spotify_url && (
                <a href={song.spotify_url} target="_blank" rel="noopener noreferrer">
                  <Button size="sm" variant="outline" className="song-action-button" data-testid="spotify-link">
                    <Play className="w-3 h-3 mr-1" />
                    Spotify
                  </Button>
                </a>
              )}
              {song.apple_music_url && (
                <a href={song.apple_music_url} target="_blank" rel="noopener noreferrer">
                  <Button size="sm" variant="outline" className="song-action-button" data-testid="apple-music-link">
                    <ExternalLink className="w-3 h-3 mr-1" />
                    Apple Music
                  </Button>
                </a>
              )}
              {showFavoriteButton && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => addToFavorites(song)}
                  className="song-action-button"
                  data-testid="add-to-favorites-button"
                >
                  <Heart className="w-3 h-3 mr-1" />
                  Favorite
                </Button>
              )}
              {showDeleteButton && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => onDelete(song.id)}
                  className="song-action-button text-red-400 hover:text-red-300"
                  data-testid="delete-button"
                >
                  <Trash2 className="w-3 h-3 mr-1" />
                  Delete
                </Button>
              )}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  );

  return (
    <div className="app-container">
      <div className="hero-section">
        <div className="logo-container">
          <div className="logo-circle">
            <Music className="w-8 h-8 text-white" />
          </div>
          <h1 className="app-title" data-testid="app-title">SongMatch</h1>
        </div>
        <p className="app-subtitle" data-testid="app-subtitle">Discover any song in seconds</p>
      </div>

      <Tabs value={activeTab} onValueChange={setActiveTab} className="tabs-container">
        <TabsList className="tabs-list">
          <TabsTrigger value="identify" className="tab-trigger" data-testid="tab-identify">
            <Sparkles className="w-4 h-4 mr-2" />
            Identify
          </TabsTrigger>
          <TabsTrigger value="history" className="tab-trigger" data-testid="tab-history">
            <Clock className="w-4 h-4 mr-2" />
            History
          </TabsTrigger>
          <TabsTrigger value="favorites" className="tab-trigger" data-testid="tab-favorites">
            <Heart className="w-4 h-4 mr-2" />
            Favorites
          </TabsTrigger>
        </TabsList>

        <TabsContent value="identify" className="tab-content">
          <div className="identify-section">
            <div className="recording-visualizer" style={{ '--audio-level': audioLevel }} data-testid="recording-visualizer">
              <div className="visualizer-circle" />
              <div className="visualizer-pulse" />
            </div>

            <Button
              onClick={isRecording ? stopRecording : startRecording}
              disabled={isIdentifying}
              className="record-button"
              data-testid="record-button"
            >
              {isRecording ? (
                <>
                  <Square className="w-6 h-6 mr-2" />
                  Stop Recording
                </>
              ) : isIdentifying ? (
                <>
                  <Sparkles className="w-6 h-6 mr-2 animate-spin" />
                  Identifying...
                </>
              ) : (
                <>
                  <Mic className="w-6 h-6 mr-2" />
                  Start Recording
                </>
              )}
            </Button>

            {identifiedSong && (
              <div className="result-section" data-testid="identified-song-result">
                <h2 className="result-title">Identified Song</h2>
                <SongCard song={identifiedSong} showFavoriteButton={true} />
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="history" className="tab-content">
          <div className="list-section" data-testid="history-list">
            <h2 className="section-title">Recent Identifications</h2>
            {history.length === 0 ? (
              <div className="empty-state" data-testid="empty-history">
                <Clock className="w-12 h-12 text-gray-500 mb-2" />
                <p className="text-gray-400">No history yet</p>
                <p className="text-sm text-gray-500">Start identifying songs to see them here</p>
              </div>
            ) : (
              <div className="songs-grid">
                {history.map((song) => (
                  <SongCard
                    key={song.id}
                    song={song}
                    showFavoriteButton={true}
                    showDeleteButton={true}
                    onDelete={deleteHistoryItem}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>

        <TabsContent value="favorites" className="tab-content">
          <div className="list-section" data-testid="favorites-list">
            <h2 className="section-title">Your Favorites</h2>
            {favorites.length === 0 ? (
              <div className="empty-state" data-testid="empty-favorites">
                <Heart className="w-12 h-12 text-gray-500 mb-2" />
                <p className="text-gray-400">No favorites yet</p>
                <p className="text-sm text-gray-500">Add songs to your favorites to see them here</p>
              </div>
            ) : (
              <div className="songs-grid">
                {favorites.map((song) => (
                  <SongCard
                    key={song.id}
                    song={song}
                    showFavoriteButton={false}
                    showDeleteButton={true}
                    onDelete={removeFromFavorites}
                  />
                ))}
              </div>
            )}
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
};

function App() {
  return (
    <div className="App">
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Home />} />
        </Routes>
      </BrowserRouter>
    </div>
  );
}

export default App;