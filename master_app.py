import asyncio
import os
from flask import Flask, jsonify, session as flask_session, redirect, url_for, request
from prometheus_client import start_http_server, Summary, Gauge
import requests
from dotenv import load_dotenv
import pandas as pd
import logging
import aiohttp
from aiohttp import ClientResponseError

from top_artists import TopArtists
from top_genres import TopGenres
from top_tracks import TopTracks

load_dotenv()

app = Flask(__name__)
app.secret_key = os.urandom(24)

SPOTIFY_CLIENT_ID = os.getenv('SPOTIFY_CLIENT_ID')
SPOTIFY_CLIENT_SECRET = os.getenv('SPOTIFY_CLIENT_SECRET')
SPOTIFY_REDIRECT_URI = os.getenv('SPOTIFY_REDIRECT_URI')

REQUEST_TIME = Summary('request_processing_seconds', 'Time spent processing request')
TOP_ARTISTS = Gauge('top_artists_by_country', 'Top artists by country', ['country', 'artist'])
TOP_GENRES = Gauge('top_genres_by_country', 'Top genres by country', ['country', 'genre'])
TOP_TRACKS = Gauge('top_tracks_by_country', 'Top tracks by country', ['country', 'track'])

logging.basicConfig(level=logging.DEBUG)

@app.route('/')
def home():
    auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={SPOTIFY_CLIENT_ID}&redirect_uri={SPOTIFY_REDIRECT_URI}&scope=user-read-private"
    return redirect(auth_url)

@app.route('/callback')
def callback():
    code = request.args.get('code')
    token_url = "https://accounts.spotify.com/api/token"
    payload = {
        'grant_type': 'authorization_code',
        'code': code,
        'redirect_uri': SPOTIFY_REDIRECT_URI,
        'client_id': SPOTIFY_CLIENT_ID,
        'client_secret': SPOTIFY_CLIENT_SECRET
    }
    headers = {
        'Content-Type': 'application/x-www-form-urlencoded'
    }
    response = requests.post(token_url, data=payload, headers=headers)
    response_data = response.json()
    access_token = response_data.get('access_token')
    flask_session['access_token'] = access_token
    return redirect(url_for('top_data'))

@app.route('/top-data')
@REQUEST_TIME.time()
def top_data():
    async def gather_data():
        async with aiohttp.ClientSession() as session:
            countries = ['US', 'ES', 'FR', 'GB', 'AU']

            top_tracks_instance = TopTracks(flask_session['access_token'])
            top_artists_instance = TopArtists(flask_session['access_token'])
            top_genres_instance = TopGenres(flask_session['access_token'])

            tasks_tracks = [top_tracks_instance.get_top_tracks(session, country) for country in countries]
            tasks_artists = [top_artists_instance.get_top_artists(session, country) for country in countries]
            tasks_genres = [top_genres_instance.get_top_genres(session, country) for country in countries]

            results_tracks = await handle_rate_limiting(tasks_tracks)
            results_artists = await handle_rate_limiting(tasks_artists)
            results_genres = await handle_rate_limiting(tasks_genres)

            return {
                'tracks': {country: tracks for country, tracks in zip(countries, results_tracks)},
                'artists': {country: artists for country, artists in zip(countries, results_artists)},
                'genres': {country: genres for country, genres in zip(countries, results_genres)}
            }

    async def handle_rate_limiting(tasks, delay=1):
        results = []
        for task in tasks:
            while True:
                try:
                    result = await task
                    results.append(result)
                    break
                except ClientResponseError as e:
                    if e.status == 429:
                        logging.error(f'Rate limit exceeded, retrying in {delay} seconds...')
                        await asyncio.sleep(delay)
                        delay = min(delay * 2, 60)  # Exponential backoff up to a max of 60 seconds
                    else:
                        logging.error(f'Failed to fetch data: {e.status}')
                        results.append(None)
                        break
        return results

    loop = asyncio.get_event_loop()
    data = loop.run_until_complete(gather_data())
    top_tracks_by_country = data['tracks']
    top_artists_by_country = data['artists']
    top_genres_by_country = data['genres']

    if not os.path.exists('data_generated'):
        os.makedirs('data_generated')

    df_tracks = pd.DataFrame([
        {'country': country, 'track': track['name'], 'artist': track['artist'], 'popularity': track['popularity']}
        for country, tracks in top_tracks_by_country.items()
        for track in tracks if track and 'name' in track and 'artist' in track and 'popularity' in track
    ])
    df_tracks.to_csv('data_generated/top_tracks_by_country.csv', index=False)
    logging.info('top_tracks_by_country.csv created successfully.')

    df_artists = pd.DataFrame([
        {'country': country, 'artist': artist['name'], 'popularity': artist['popularity']}
        for country, artists in top_artists_by_country.items()
        for artist in artists if artist and 'name' in artist and 'popularity' in artist
    ])
    df_artists.to_csv('data_generated/top_artists_by_country.csv', index=False)
    logging.info('top_artists_by_country.csv created successfully.')

    df_genres = pd.DataFrame([
        {'country': country, 'genre': genre['name'], 'popularity': genre['popularity']}
        for country, genres in top_genres_by_country.items()
        for genre in genres if genre and 'name' in genre and 'popularity' in genre
    ])
    df_genres.to_csv('data_generated/top_genres_by_country.csv', index=False)
    logging.info('top_genres_by_country.csv created successfully.')

    # Update Prometheus Gauges
    for country, tracks in top_tracks_by_country.items():
        for track in tracks:
            TOP_TRACKS.labels(country=country, track=track['name']).set(track['popularity'])

    for country, artists in top_artists_by_country.items():
        for artist in artists:
            TOP_ARTISTS.labels(country=country, artist=artist['name']).set(artist['popularity'])

    for country, genres in top_genres_by_country.items():
        for genre in genres:
            TOP_GENRES.labels(country=country, genre=genre['name']).set(genre['popularity'])

    return jsonify({
        'top_tracks_by_country': top_tracks_by_country,
        'top_artists_by_country': top_artists_by_country,
        'top_genres_by_country': top_genres_by_country
    })

if __name__ == '__main__':
    start_http_server(8000)
    app.run(debug=True, host='0.0.0.0', port=5000)
