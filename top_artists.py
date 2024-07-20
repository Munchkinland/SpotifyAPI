import aiohttp
import logging

class TopArtists:
    def __init__(self, access_token):
        self.access_token = access_token

    async def get_top_artists(self, session, country):
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        url = f'https://api.spotify.com/v1/search?q=top artists&type=artist&market={country}&limit=10'
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('artists', {}).get('items', [])
            else:
                logging.error(f'Failed to fetch data from {url}: {response.status}')
                return []
