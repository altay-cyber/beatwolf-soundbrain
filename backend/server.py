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
            data = aiohttp.FormData()
            data.add_field('file', open(temp_path, 'rb'), filename='audio.wav')
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