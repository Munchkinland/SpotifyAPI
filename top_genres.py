import aiohttp
import logging

class TopGenres:
    def __init__(self, access_token):
        self.access_token = access_token

    async def get_top_genres(self, session, country):
        headers = {
            'Authorization': f'Bearer {self.access_token}'
        }
        url = f'https://api.spotify.com/v1/search?q=top genres&type=genre&market={country}&limit=10'
        async with session.get(url, headers=headers) as response:
            if response.status == 200:
                data = await response.json()
                return data.get('genres', {}).get('items', [])
            else:
                logging.error(f'Failed to fetch data from {url}: {response.status}')
                return []
