from fastapi import FastAPI, APIRouter, File, UploadFile, HTTPException
from dotenv import load_dotenv
from starlette.middleware.cors import CORSMiddleware
from motor.motor_asyncio import AsyncIOMotorClient
import os
import logging
from pathlib import Path
from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional
import uuid
from datetime import datetime, timezone
import aiohttp
import tempfile
from emergentintegrations.llm.chat import LlmChat, UserMessage
import spotipy
from spotipy.oauth2 import SpotifyClientCredentials
import json

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

# MongoDB connection
mongo_url = os.environ['MONGO_URL']
client = AsyncIOMotorClient(mongo_url)
db = client[os.environ['DB_NAME']]

# Create the main app without a prefix
app = FastAPI()

# Create a router with the /api prefix
api_router = APIRouter(prefix="/api")

# AudD API configuration
AUDD_API_KEY = "07f6b854581b8a775d81666e3991d45a"
AUDD_API_URL = "https://api.audd.io/"

# Define Models
class SongIdentification(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    artist: str
    album: Optional[str] = None
    release_date: Optional[str] = None
    artwork: Optional[str] = None
    preview_url: Optional[str] = None
    spotify_url: Optional[str] = None
    apple_music_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class SongIdentificationCreate(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    release_date: Optional[str] = None
    artwork: Optional[str] = None
    preview_url: Optional[str] = None
    spotify_url: Optional[str] = None
    apple_music_url: Optional[str] = None

class Favorite(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    title: str
    artist: str
    album: Optional[str] = None
    release_date: Optional[str] = None
    artwork: Optional[str] = None
    preview_url: Optional[str] = None
    spotify_url: Optional[str] = None
    apple_music_url: Optional[str] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

class FavoriteCreate(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    release_date: Optional[str] = None
    artwork: Optional[str] = None
    preview_url: Optional[str] = None
    spotify_url: Optional[str] = None
    apple_music_url: Optional[str] = None

@api_router.get("/")
async def root():
    return {"message": "Song Recognition API Ready"}

@api_router.post("/identify")
async def identify_song(file: UploadFile = File(...)):
    try:
        # Determine file extension
        file_ext = ".webm" if "webm" in file.content_type else ".wav"
        
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=file_ext) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_path = temp_file.name
        
        # Call AudD API
        async with aiohttp.ClientSession() as session:
            with open(temp_path, 'rb') as audio_file:
                data = aiohttp.FormData()
                filename = f'audio{file_ext}'
                data.add_field('file', audio_file, filename=filename, content_type=file.content_type or 'audio/webm')
                data.add_field('api_token', AUDD_API_KEY)
                data.add_field('return', 'apple_music,spotify')
                
                async with session.post(AUDD_API_URL, data=data) as response:
                    result = await response.json()
        
        # Clean up temp file
        os.unlink(temp_path)
        
        if result.get('status') != 'success':
            raise HTTPException(status_code=400, detail="Song not recognized")
        
        song_data = result.get('result')
        if not song_data:
            raise HTTPException(status_code=404, detail="No match found")
        
        # Extract song information
        song_info = {
            "title": song_data.get('title', 'Unknown'),
            "artist": song_data.get('artist', 'Unknown'),
            "album": song_data.get('album', None),
            "release_date": song_data.get('release_date', None),
            "artwork": song_data.get('spotify', {}).get('album', {}).get('images', [{}])[0].get('url') if song_data.get('spotify') else None,
            "preview_url": song_data.get('spotify', {}).get('preview_url') if song_data.get('spotify') else None,
            "spotify_url": song_data.get('spotify', {}).get('external_urls', {}).get('spotify') if song_data.get('spotify') else None,
            "apple_music_url": song_data.get('apple_music', {}).get('url') if song_data.get('apple_music') else None
        }
        
        # Save to history
        song_obj = SongIdentification(**song_info)
        doc = song_obj.model_dump()
        doc['timestamp'] = doc['timestamp'].isoformat()
        await db.history.insert_one(doc)
        
        return song_obj
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Error identifying song: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing audio: {str(e)}")

@api_router.get("/history", response_model=List[SongIdentification])
async def get_history():
    history = await db.history.find({}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    
    for item in history:
        if isinstance(item['timestamp'], str):
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
    
    return history

@api_router.delete("/history/{song_id}")
async def delete_history_item(song_id: str):
    result = await db.history.delete_one({"id": song_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="History item not found")
    return {"message": "History item deleted"}

@api_router.post("/favorites", response_model=Favorite)
async def add_favorite(favorite: FavoriteCreate):
    # Check if already in favorites
    existing = await db.favorites.find_one({"title": favorite.title, "artist": favorite.artist})
    if existing:
        raise HTTPException(status_code=400, detail="Already in favorites")
    
    favorite_obj = Favorite(**favorite.model_dump())
    doc = favorite_obj.model_dump()
    doc['timestamp'] = doc['timestamp'].isoformat()
    await db.favorites.insert_one(doc)
    
    return favorite_obj

@api_router.get("/favorites", response_model=List[Favorite])
async def get_favorites():
    favorites = await db.favorites.find({}, {"_id": 0}).sort("timestamp", -1).to_list(100)
    
    for item in favorites:
        if isinstance(item['timestamp'], str):
            item['timestamp'] = datetime.fromisoformat(item['timestamp'])
    
    return favorites

@api_router.delete("/favorites/{favorite_id}")
async def delete_favorite(favorite_id: str):
    result = await db.favorites.delete_one({"id": favorite_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Favorite not found")
    return {"message": "Favorite removed"}

# AI Playlist Generator Models
class PlaylistGenerateRequest(BaseModel):
    mood: Optional[str] = None
    prompt: Optional[str] = None

class PlaylistTrack(BaseModel):
    title: str
    artist: str
    album: Optional[str] = None
    artwork: Optional[str] = None
    spotify_url: Optional[str] = None
    preview_url: Optional[str] = None

class GeneratedPlaylist(BaseModel):
    model_config = ConfigDict(extra="ignore")
    
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    description: str
    tracks: List[PlaylistTrack]
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# AI Playlist Generator Endpoints
@api_router.post("/playlist/generate")
async def generate_playlist(request: PlaylistGenerateRequest):
    try:
        # Initialize Claude Sonnet 4
        llm_key = os.environ.get('EMERGENT_LLM_KEY')
        chat = LlmChat(
            api_key=llm_key,
            session_id=str(uuid.uuid4()),
            system_message="You are a music expert who creates amazing playlists. Generate song recommendations based on user preferences."
        ).with_model("anthropic", "claude-4-sonnet-20250514")
        
        # Create prompt based on mood or custom prompt
        if request.mood:
            user_prompt = f"Create a playlist of 10 songs for the mood: {request.mood}. Include a mix of popular and lesser-known tracks. Return ONLY a JSON array with format: {{\"songs\": [{{\"title\": \"song name\", \"artist\": \"artist name\"}}]}}"
        elif request.prompt:
            user_prompt = f"Create a playlist of 10 songs based on: {request.prompt}. Return ONLY a JSON array with format: {{\"songs\": [{{\"title\": \"song name\", \"artist\": \"artist name\"}}]}}"
        else:
            raise HTTPException(status_code=400, detail="Either mood or prompt is required")
        
        # Get AI recommendations
        message = UserMessage(text=user_prompt)
        ai_response = await chat.send_message(message)
        
        logger.info(f"AI Response: {ai_response}")
        
        # Parse JSON from response
        try:
            # Extract JSON from response
            response_text = ai_response.strip()
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0].strip()
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0].strip()
            
            songs_data = json.loads(response_text)
            if "songs" in songs_data:
                songs_list = songs_data["songs"]
            else:
                songs_list = songs_data
        except Exception as e:
            logger.error(f"Error parsing AI response: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to parse AI recommendations")
        
        # Initialize Spotify (no auth needed for search)
        sp = spotipy.Spotify(client_credentials_manager=SpotifyClientCredentials(
            client_id=os.environ.get('SPOTIFY_CLIENT_ID', ''),
            client_secret=os.environ.get('SPOTIFY_CLIENT_SECRET', '')
        )) if os.environ.get('SPOTIFY_CLIENT_ID') else None
        
        # Enrich with Spotify data
        tracks = []
        for song in songs_list[:10]:  # Limit to 10
            track_data = {
                "title": song.get("title", "Unknown"),
                "artist": song.get("artist", "Unknown"),
                "album": None,
                "artwork": None,
                "spotify_url": None,
                "preview_url": None
            }
            
            # Try to get Spotify data
            if sp:
                try:
                    query = f"{song.get('title')} {song.get('artist')}"
                    results = sp.search(q=query, limit=1, type='track')
                    if results['tracks']['items']:
                        spotify_track = results['tracks']['items'][0]
                        track_data["album"] = spotify_track['album']['name']
                        if spotify_track['album']['images']:
                            track_data["artwork"] = spotify_track['album']['images'][0]['url']
                        track_data["spotify_url"] = spotify_track['external_urls']['spotify']
                        track_data["preview_url"] = spotify_track.get('preview_url')
                except Exception as e:
                    logger.error(f"Spotify search error for {song}: {str(e)}")
            
            tracks.append(PlaylistTrack(**track_data))
        
        # Create playlist object
        playlist_name = f"{request.mood.title()} Playlist" if request.mood else "Custom Playlist"
        playlist_desc = f"AI-generated playlist for {request.mood} mood" if request.mood else f"AI-generated playlist: {request.prompt}"
        
        playlist = GeneratedPlaylist(
            name=playlist_name,
            description=playlist_desc,
            tracks=tracks
        )
        
        # Save to database
        doc = {
            "id": playlist.id,
            "name": playlist.name,
            "description": playlist.description,
            "tracks": [track.model_dump() for track in playlist.tracks],
            "created_at": playlist.created_at.isoformat()
        }
        await db.playlists.insert_one(doc)
        
        return playlist
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating playlist: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error generating playlist: {str(e)}")

@api_router.get("/playlist/list", response_model=List[GeneratedPlaylist])
async def list_playlists():
    playlists = await db.playlists.find({}, {"_id": 0}).sort("created_at", -1).to_list(50)
    
    for playlist in playlists:
        if isinstance(playlist['created_at'], str):
            playlist['created_at'] = datetime.fromisoformat(playlist['created_at'])
    
    return playlists

@api_router.delete("/playlist/{playlist_id}")
async def delete_playlist(playlist_id: str):
    result = await db.playlists.delete_one({"id": playlist_id})
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Playlist not found")
    return {"message": "Playlist deleted"}

# Include the router in the main app
app.include_router(api_router)

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=os.environ.get('CORS_ORIGINS', '*').split(','),
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@app.on_event("shutdown")
async def shutdown_db_client():
    client.close()