from requests import post, get
from bs4 import BeautifulSoup
import requests
import json
from dotenv import load_dotenv
import os
from flask import Flask, request, redirect, render_template, url_for

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
import time

app = Flask(__name__)

load_dotenv()

client_id = os.getenv("CLIENT_ID")
client_secret = os.getenv("CLIENT_SECRET")
redirect_uri = os.getenv("REDIRECT_URI") 
port = os.getenv("PORT")

class SpotifyApi:
    def __init__(self):
        self.token = None

    def get_auth_url(self):
        scope = "user-read-recently-played user-follow-read user-library-read user-follow-modify"
        auth_url = f"https://accounts.spotify.com/authorize?response_type=code&client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}"
        return auth_url

    def get_token(self, auth_code):
        url = "https://accounts.spotify.com/api/token"
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        data = {
            "grant_type": "authorization_code",
            "code": auth_code,
            "redirect_uri": redirect_uri,
            "client_id": client_id,
            "client_secret": client_secret
        }
        result = post(url, headers=headers, data=data)
        
        if result.status_code != 200:
            print(f"Error getting token: {result.content}")
            return None
        
        json_result = json.loads(result.content)
        self.token = json_result["access_token"]
        return self.token
    
    def get_auth_header(self):
        return {"Authorization": "Bearer " + self.token}

    def search_for_artist(self, artist_name):
        if artist_name:
            try:
                url = "https://api.spotify.com/v1/search?"
                headers = self.get_auth_header()
                query = f"q={artist_name}&type=artist&limit=1"
                
                query_url = url + query
                result = get(query_url, headers=headers)
                
                if result.status_code != 200:
                    print(f"Error searching for artist: {result.content}")
                    return None
                
                json_result = json.loads(result.content)
                
                print("working here...")
                print(json_result)
                
                if "artists" not in json_result or not json_result["artists"]["items"]:
                    print("Artist name does not exist...")
                    return None

                artist_data = json_result["artists"]["items"][0]
                num_of_followers = artist_data["followers"]["total"] if artist_data.get("followers") else None
                
                return {
                    "id": artist_data["id"],
                    "name": artist_data["name"],
                    "images": artist_data["images"],
                    "followers": format(num_of_followers, ",")
                }
                
            except Exception as e:
                print(f"An error occurred: {e}")
                return None
            
        return None
    
    def get_artist_id(self, artist_data):
        return artist_data["id"] 
    
    def get_artist_name(self, artist_data):
        return artist_data["name"]
    
    def get_artist_image(self, artist_data):
        return artist_data["images"][0]["url"] if artist_data and "images" in artist_data and artist_data["images"] else None

    def get_artist_about(self, artist_id):
        url = f'https://open.spotify.com/artist/{artist_id}' 
    
        response = requests.get(url)
        html_content = response.content
   
        soup = BeautifulSoup(html_content, 'html.parser')

        div_element = soup.find('div', class_='Zbad_ytC5aqG3ZISd4Gw')

        if div_element:
            span_element = div_element.find('span')
            
            if span_element:
                text_content = span_element.get_text(strip=True)  # strip=True removes leading/trailing whitespace
                return text_content
            else:
                print("Span element not found.")
        else:
            print("Div element not found.")
            
    def convert_milliseconds_to_string(self, milliseconds):
        # Convert milliseconds to seconds
        seconds = milliseconds / 1000
        
        # Calculate hours, minutes, and remaining seconds
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        remaining_seconds = int(seconds % 60)
        
        # Return formatted string
        return f"{hours}h {minutes}m {remaining_seconds}s"

    def get_songs_by_artist(self, artist_id):
        url = f"https://api.spotify.com/v1/artists/{artist_id}/top-tracks?country=PH"
        headers = self.get_auth_header()
        
        output = []
        
        result = get(url, headers=headers)
        
        if result.status_code != 200:
            print(f"Error getting songs: {result.content}")
            return None
        
        json_result = json.loads(result.content)
        print(json_result)

        data = json_result["tracks"]
        
        for song in data[:7]:
            output.append({
                "name": song["name"],
                "duration_ms": self.convert_milliseconds_to_string(song["duration_ms"])
            })
        
        return output
    
    def get_song_duration_and_listeners(self, artist_id):
        url = f"https://open.spotify.com/artist/{artist_id}"
        response = requests.get(url)
        songs = []
        songs = self.get_songs_by_artist(artist_id)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            
            spans = soup.find_all('span', class_='Hj3ST6Lg66UEtynHfOT8')
            paragraphs = soup.find_all('p', class_='e-9640-text encore-text-body-small encore-internal-color-text-subdued ListRowDetails__ListRowDetailText-sc-sozu4l-0 hxCObm')

            results = []
            
            for span, paragraph, song in zip(spans, paragraphs, songs):
                title =  span.text.strip()
                plays = paragraph.text.strip()

                duration_ms = song["duration_ms"]
                total_seconds = duration_ms / 1000

                minutes = int(total_seconds // 60)
                seconds = int(total_seconds % 60)

                formatted_duration = f"{minutes}:{seconds:02d}"

                results.append({
                    "title": title,
                    "plays": plays,
                    "duration": formatted_duration
                })
            
            return results
        
        return None

    def get_recently_played_tracks(self):
        url = "https://api.spotify.com/v1/me/player/recently-played"
        headers = self.get_auth_header()
        
        result = get(url, headers=headers)
        
        if result.status_code != 200:
            print(f"Error getting recently played tracks: {result.content}")
            return None
        
        recently_played_tracks = json.loads(result.content)["items"]
        
        artist_play_count = {}

        for track in recently_played_tracks:
            track_artists = track['track']['artists']
            
            for artist in track_artists:
                artist_name = artist['name']
                if artist_name in artist_play_count:
                    artist_play_count[artist_name] += 1
                else:
                    artist_play_count[artist_name] = 1
        
        return artist_play_count 
    
    def getTop5Tracks(self):
        url = "https://api.spotify.com/v1/me/player/recently-played"
        headers = self.get_auth_header()
        
        result = get(url, headers=headers)
        
        if result.status_code != 200:
            print(f"Error getting recently played tracks: {result.content}")
            return None
        
        recently_played_tracks = json.loads(result.content)["items"]
        
        track_play_count = {}  # Dictionary to keep track of play counts

        for track in recently_played_tracks:
            track_name = track['track']['name']
            track_id = track['track']['id']
            album_image = track['track']['album']['images'][0]['url'] if track['track']['album']['images'] else None
            
            # Increment the play count for the track
            if track_id in track_play_count:
                track_play_count[track_id]['count'] += 1
            else:
                track_play_count[track_id] = {
                    "name": track_name,
                    "image": album_image,
                    "count": 1
                }
        
        # Sort the tracks by play count in descending order and get the top 5
        sorted_tracks = sorted(track_play_count.values(), key=lambda x: x['count'], reverse=True)[:5]
        
        return sorted_tracks
    
    def getRecentlyPlayedTracks(self):
        url = "https://api.spotify.com/v1/me/player/recently-played"
        headers = self.get_auth_header()
        
        result = get(url, headers=headers)
        
        if result.status_code != 200:
            print(f"Error getting recently played tracks: {result.content}")
            return None
        
        recently_played_tracks = json.loads(result.content)["items"]
        
        track_info_list = []
        seen_tracks = set()  # Set to keep track of seen track IDs

        for track in recently_played_tracks[:12]:
            track_name = track['track']['name']
            track_id = track['track']['id']
            album_image = track['track']['album']['images'][0]['url'] if track['track']['album']['images'] else None

            if track_id not in seen_tracks:
                seen_tracks.add(track_id) 
                
                track_info = {
                    "name": track_name,
                    "id": track_id,
                    "image": album_image
                }
                
                track_info_list.append(track_info)
        
        return track_info_list

    def get_followed_artists(self):
        url = "https://api.spotify.com/v1/me/following?type=artist&limit=5" 
        headers = self.get_auth_header()
        
        result = get(url, headers=headers)
        
        if result.status_code != 200:
            print(f"Error getting followed artists: {result.content}")
            return None
        
        json_result = json.loads(result.content)
        
        return [{
            "id": artist["id"],
            "name": artist["name"],
            "genres": artist["genres"],
            "popularity": artist["popularity"],
            "external_url": artist["external_urls"]["spotify"],
            "image": artist["images"][0]["url"] if artist["images"] else None
        } for artist in json_result["artists"]["items"]]
        
    def get_artist_banner(self, artist_id):
        url = f"https://open.spotify.com/artist/{artist_id}"
        r = requests.get(url)

        soup = BeautifulSoup(r.text, 'html.parser')

        monthly_listeners_span = soup.find('span', class_='Ydwa1P5GkCggtLlSvphs')

        if monthly_listeners_span:
            monthly_listeners_text = monthly_listeners_span.text
            monthly_listeners = monthly_listeners_text.split()[0] 
            print(monthly_listeners)
        else:
            print("Element not found")
            
    def today_biggest_hit(self):
        url = 'https://open.spotify.com/'

        response = requests.get(url)

        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
        
            span_elements = soup.find_all('span', class_='ListRowTitle__LineClamp-sc-1xe2if1-0')

            results = []
 
            for index, span in enumerate(span_elements):
                if index >= 5:
                    break
                img_element = span.find_previous('img', class_='Image-sc-1u215sg-3')
                
                if img_element and 'src' in img_element.attrs:
                    results.append({
                        'src': img_element['src'],
                        'text': span.get_text(strip=True)
                    })
            return results
        else:
            print(f"Failed to retrieve content. Status code: {response.status_code}")
        
    def follow_artist(self, artist_id):
        print(f"FOLLOW TOKEN {self.token}")
        url = f"https://api.spotify.com/v1/me/following?type=artist&ids={artist_id}"
        headers = {
            "Authorization": "Bearer " + self.token,
            "Content-Type": "application/json"
        }
        
        response = requests.put(url, headers=headers)

        print(response.status_code)
        print(response.content)

        if response.status_code == 204:
            print("You followed the artist")
            return True 
        else:
            print("Failed to follow artist")
            return False
        
    def unfollow_artist(self, artist_id):
        url = f"https://api.spotify.com/v1/me/following?type=artist&ids={artist_id}"
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }
        
        response = requests.delete(url, headers=headers)
        
        if response.status_code == 204:
            print("You unfollowed the artist")
            return True
        else:
            print("Failed to unfollow artist")
            return False
        
    def if_following_artist(self, artist_id):
        url = f"https://api.spotify.com/v1/me/following/contains?type=artist&ids={artist_id}"
        headers = self.get_auth_header()
        
        response = requests.get(url, headers=headers)
        
        if response.status_code == 200:
            result = json.loads(response.content)
            return result[0] if result else False
        else:
            print("Error in if_following_artist function")
        
    def get_artist_monthly_listeners(self, artist_id):
        url = f'https://open.spotify.com/artist/{artist_id}'

        response = requests.get(url)
        html_content = response.text

        soup = BeautifulSoup(html_content, 'html.parser')

        span = soup.find('div', class_='fjP8GyQyM5IWQvTxWk6W')

        if span:
            monthly_listeners = span.text
            return monthly_listeners
        else:
            return
    
    def get_top_played_artists_data(self, top_played_artists):
        top_artists = []
        for top_artist, count in top_played_artists[:5]:
            artist_info = self.search_for_artist(top_artist) 
            artist_pfp = self.get_artist_image(artist_info) 

            top_artists.append({
                "artist": top_artist,
                "image": artist_pfp,
                "count": f"{count:,}"
            })
            
        return top_artists
        
    def get_saved_albums(self):
        url = 'https://api.spotify.com/v1/me/albums'
        headers = {
            'Authorization': f'Bearer {self.token}',
            'Content-Type': 'application/json'
        }
        query = "?offset=0&limit=8"
        query_url = url + query
        albums = []

        response = requests.get(query_url, headers=headers)
        
        if response.status_code != 200:
            print(f"Error: {response.status_code} - {response.text}")
            return []
        
        data = response.json()
        items = data.get('items', [])
        
        if not items:
            return []
        
        for item in items:
            album_name = item['album']['name']
            album_image_url = item['album']['images'][0]['url'] if item['album']['images'] else None
            albums.append({'name': album_name, 'image_url': album_image_url})

        return albums
        
spotify_api = SpotifyApi()

@app.route('/')
def index():
    auth_url = spotify_api.get_auth_url()
    return render_template('main.html', auth_url=auth_url)

@app.route('/logout')
def logout():
    spotify_api.token = None
    return redirect('/')

# callback from auth_url
# * by opening auth_url, spotify service will go to this route and will pass the authentication code as params
# * 127.0.0.1:5000
@app.route('/callback')
def callback():
    try: 
        auth_code = request.args.get('code')
        token = spotify_api.get_token(auth_code)
        
        if token:
            print("Token retrieved successfully.")
            return redirect('/home')
        else:
            print("Failed to retrieve token.")
            return redirect('/')
    except Exception as e:
        print(f"Error in callback route : {e}")

@app.route('/home', methods=['GET', 'POST'])
def home():
    if spotify_api.token:
        popular_artist = spotify_api.today_biggest_hit()
        followed_artists = spotify_api.get_followed_artists()
        top_recently_played_songs = spotify_api.getTop5Tracks()
        recentlyPlayedTracks = spotify_api.getRecentlyPlayedTracks()
        albums = spotify_api.get_saved_albums()
  
        get_artist = request.form.get('artist_name') 
        artist_data = spotify_api.search_for_artist(get_artist)
        
        current_artist_name = request.args.get('artist_name')
        current_artist_id = request.args.get('artist_id')
        
        current_artist_data = spotify_api.search_for_artist(current_artist_name)

        songs = []
        artist = {}
        artist_id = None
        
        following_artist = None
        
        if current_artist_id and artist_data is None:
            artist_id = current_artist_id
            
            songs = spotify_api.get_songs_by_artist(artist_id)
            following_artist = spotify_api.if_following_artist(artist_id)
            
            artist = {
                "id": spotify_api.get_artist_id(current_artist_data),
                "name": spotify_api.get_artist_name(current_artist_data),
                "image": spotify_api.get_artist_image(current_artist_data),
                "about": spotify_api.get_artist_about(artist_id),
                "monthly_listeners": spotify_api.get_artist_monthly_listeners(current_artist_data["id"])
            }
        elif artist_data is not None:
            artist_id = artist_data["id"]
        
        if artist_data is not None:
            songs = spotify_api.get_songs_by_artist(artist_id)
            following_artist = spotify_api.if_following_artist(artist_id)
            
            artist = {
                "id": spotify_api.get_artist_id(artist_data),
                "name": spotify_api.get_artist_name(artist_data),
                "image": spotify_api.get_artist_image(artist_data),
                "about": spotify_api.get_artist_about(artist_id),
                "monthly_listeners": spotify_api.get_artist_monthly_listeners(artist_data["id"])
            }
        
        return render_template('home.html',artist_data=artist_data, artist_id=artist_id, artist=artist, songs=songs, followed_artists=followed_artists, following_artist=following_artist, popular_artist=popular_artist, top_recently_played_songs=top_recently_played_songs, recentlyPlayedTracks=recentlyPlayedTracks, albums=albums)
    return redirect('/')

@app.route('/wrapped')
def wrapped():
    if spotify_api.token:
        top_recently_played_songs = spotify_api.getTop5Tracks()

        artist_play_count = spotify_api.get_recently_played_tracks()
        
        top_played_artists = sorted(artist_play_count.items(), key=lambda x: x[1], reverse=True)[:10]
        spotify_wrapped = spotify_api.get_top_played_artists_data(top_played_artists)

        return render_template('wrapped.html', spotify_wrapped=spotify_wrapped, top_recently_played_songs=top_recently_played_songs)
    return redirect('/')

@app.route('/followArtist', methods=['POST'])
def followArtist():
    if spotify_api.token:
        artist_id = request.form.get('artist_id')
        artist_name = request.form.get('artist_name')

        if artist_id:
            spotify_api.follow_artist(artist_id)
        
        return redirect(url_for('home', artist_id=artist_id, artist_name=artist_name))
    print("Missing token in followArtist function", "error")
    return redirect('/')

@app.route('/unfollowArtist', methods=['POST'])
def unfollowArtist():
    if spotify_api.token:
        artist_id = request.form.get('artist_id')
        artist_name = request.form.get('artist_name')
        
        if artist_id:
            spotify_api.unfollow_artist(artist_id)
            
        return redirect(url_for('home', artist_id=artist_id, artist_name=artist_name))

if __name__ == '__main__':
    app.run(port=port, debug=True)
    