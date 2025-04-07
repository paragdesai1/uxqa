from fastapi import FastAPI, File, UploadFile, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from typing import Optional
import requests
import uvicorn
import os
import asyncio
from playwright.async_api import async_playwright
from PIL import Image, ImageChops

app = FastAPI()

# Mount static file serving for screenshot previews
app.mount("/", StaticFiles(directory="."), name="static")

# Allow CORS for local dev
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Load Figma API token securely
FIGMA_TOKEN = os.getenv("FIGMA_TOKEN", "figd_jHWWTRa9WEGSQIaKvKgYSx3hyh8omAN6AtDWP_lL")

# Fetch Figma file JSON

def fetch_figma_file_data(file_key: str):
    headers = {"X-Figma-Token": FIGMA_TOKEN}
    url = f"https://api.figma.com/v1/files/{file_key}"
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        return response.json()
    else:
        return {"error": f"Figma API error {response.status_code}"}

# Placeholder endpoint for health check
@app.get("/")
def read_root():
    return {"message": "UX QA Tool is running"}
