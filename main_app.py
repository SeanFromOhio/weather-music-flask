from flask import Flask, render_template, url_for, request, redirect, jsonify
from flask_sqlalchemy import SQLAlchemy
import flask
import flask_login
import requests
from forms import SignupForm, LoginForm
from flask_login import logout_user, LoginManager, UserMixin, login_user, login_required
from datetime import datetime
import re
import os

# Initialize the db with SQLAlchemy
app = Flask(__name__)
app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///WxMusic.db"
app.config["SECRET_KEY"] = os.environ.get("flask_key")
db = SQLAlchemy(app)

# Flask login management system
login_manager = LoginManager()
login_manager.login_view = "/login"
login_manager.init_app(app)


# Creating the user current_user object
@login_manager.user_loader
def load_user(user_id):
    return User.query.get(user_id)


# User Model -----------------------------
class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(30), unique=True, nullable=False)
    password = db.Column(db.String(30), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)
    songs = db.relationship("SongList", backref="author", lazy=True)

    def __repr__(self):
        return f"Username: '{self.username}'({self.id}) - Account Created: '{self.date_created}"


# User Song Model ------------------------
class SongList(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    song_name = db.Column(db.String, unique=False, nullable=False)
    song_url = db.Column(db.String, unique=False, nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    date_created = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f"{self.user_id} - {self.song_name}"


# Main processing and landing page
@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == "POST":
        form_check_geo = request.form.get("hidden_lat", None)  # Needed to check if the geolocation form was submitted

        # This checks which form was submitted; geolocation or the zip code form
        if form_check_geo:
            # Form accessing user location using HTML5 Geolocation API
            user_lat = request.form["hidden_lat"]
            user_long = request.form["hidden_long"]
            user_coords = user_lat + "," + user_long
            #print(user_coords)

        else:
            # Used Google's geocoding API, which takes the user zip code input and outputs the lat/long of that location
            google_api_key = os.environ.get("google_geocode_key")  # MAKE SURE THIS IS HIDDEN WHEN IN PRODUCTION
            user_zip = request.form["user_zip"]
            zip_code_coords_url = "https://maps.googleapis.com/maps/api/geocode/json?address=" + user_zip \
                                  + "%20USA&key=" + google_api_key
            #print(zip_code_coords_url)

            coords_data = requests.get(zip_code_coords_url)  # API request
            coords_data_json = coords_data.json()  # Necessary to access the data as a dictionary (json...)

            # Checks if the user entered a valid zip code, if not it tells the user to try again.
            if coords_data_json["status"] == "ZERO_RESULTS":
                flask.flash('That is not a valid Zip Code (US), please try again!')
                return render_template("index.html")

            elif coords_data_json["results"][0]["address_components"][-1]["short_name"] != "US":
                flask.flash('Currently only US Zip Codes are allowed, please try again!')
                return render_template("index.html")

            else:
                user_lat = str(coords_data_json["results"][0]["geometry"]["location"]["lat"])
                user_long = str(coords_data_json["results"][0]["geometry"]["location"]["lng"])
                user_coords = user_lat + "," + user_long  # Format to be used in the NWS API

        # User user coordinates to access National Weather Service (NWS) API
        # First, must find closest weather observation station using the following url:
        NWS_stations_url = ("https://api.weather.gov/points/" + user_coords + "/stations")
        #print(NWS_stations_url)

        # Next, read the JSON data and access key/value pair that houses our specific weather station data
        station_data = requests.get(NWS_stations_url)  # requests library not to be mistaken for flask-request
        try:
            station_data_json = station_data.json()  # Houses our needed data
        except:
            flask.flash("The National Weather Service API is currently down, meaning no weather data."
                        " It will be back up soon!")
            return render_template("index.html")

        # Access the json data and grabs the needed url with the necessary page added on
        wx_observ_url = station_data_json["features"][0]["id"] + "/observations/latest"
        print(wx_observ_url)

        # Now we have all the wx data from the closest observation station
        wx_data = requests.get(wx_observ_url)
        # NWS API goes down from time to time, so let's catch that error:
        try:
            wx_data_json = wx_data.json()
        except:
            flask.flash("The Weather API is currently down, meaning no weather data. It will be back up soon!")
            return render_template("index.html")

        # Grab the specific weather text description, could be multiple elements.
        # Check if presentWeather has data, if not it implies there's no precipitation occurring, therefore it's
        # sunny or cloudy. Thus, we utilize textDescription is order to determine which.
        present_weather_len = len(wx_data_json["properties"]["presentWeather"])
        if present_weather_len > 0:
            wx_text_description = wx_data_json["properties"]["presentWeather"][0]["rawString"]
        else:
            wx_text_description = wx_data_json["properties"]["textDescription"]

        # The filters are needed as similar conditions have different names. The rawStrings are an easy
        # identifier for the type of precipitation or weather effect (Thunderstorms...)
        sun_words_filter = re.compile(r'\b(Sun|Clear|Fair)\b').search
        cloud_words_filter = re.compile(r'\b(Clouds|Cloudy|FG|HZ)\b').search
        rain_rawstring_filter = re.compile(r'\b(RA|BR|DZ|SH)\b').search
        storm_rawstring_filter = re.compile(r'\b(TS|FC|GR|)\b').search
        snow_rawstring_filter = re.compile(r'\b(SN|SW|SP|SG|S|FZRA|SNINCR)\b').search

        # Lastly, the weather information is needed to be passed into the following pages accordingly.
        # Current temperature (if there's a measured temperature...):
        try:
            current_temp_C = wx_data_json["properties"]["temperature"]["value"]
            #print(current_temp_C)
            current_temp_F = round((current_temp_C * (9 / 5)) + 32)  # Convert to fahrenheit
        except:
            current_temp_F = "Null "

        # Weather description:
        current_conditions = wx_data_json["properties"]["textDescription"]
        # Weather icon:
        current_icon_url = wx_data_json["properties"]["icon"]

        # Lat / Long to hyperlink to NWS website for specific location:
        lat = round(wx_data_json["geometry"]["coordinates"][1], 2)
        long = round(wx_data_json["geometry"]["coordinates"][0], 2)
        nws_website = ("https://forecast.weather.gov/MapClick.php?textField1=" + str(lat) + "&textField2=" + str(long))
        #print(nws_website)

        # Conditionals utilizing regular expressions to hunt for a word match from the NWS data which then
        # redirects to the appropriate page. Template comments/explanation can be found under the sun.html template.
        if cloud_words_filter(wx_text_description):
            print("Cloud")
            return render_template("weather_playlist/cloud.html", current_temp_F=current_temp_F,
                                   current_conditions=current_conditions, current_icon_url=current_icon_url,
                                   nws_website=nws_website)
        elif sun_words_filter(wx_text_description):
            print("Sun")
            return render_template("weather_playlist/sun.html", current_temp_F=current_temp_F,
                                   current_conditions=current_conditions, current_icon_url=current_icon_url,
                                   nws_website=nws_website)
        elif snow_rawstring_filter(wx_text_description):
            print("Snow")
            return render_template("weather_playlist/snow.html", current_temp_F=current_temp_F,
                                   current_conditions=current_conditions, current_icon_url=current_icon_url,
                                   nws_website=nws_website)
        elif rain_rawstring_filter(wx_text_description):
            print("Rain")
            return render_template("weather_playlist/rain.html", current_temp_F=current_temp_F,
                                   current_conditions=current_conditions, current_icon_url=current_icon_url,
                                   nws_website=nws_website)
        elif storm_rawstring_filter(wx_text_description):
            print("Storm")
            return render_template("weather_playlist/storm.html", current_temp_F=current_temp_F,
                                   current_conditions=current_conditions, current_icon_url=current_icon_url,
                                   nws_website=nws_website)
        return render_template("index.html")
    else:
        return render_template("index.html")


# Using YouTube Data API to construct a list with all my songs from a specified playlist - CURRENTLY NOT UTILIZED
# def get_playlist_titles(playlist_id):
#     google_api_key = "os.environ.get("google_geocode_key")"  # MAKE SURE THIS IS HIDDEN WHEN IN PRODUCTION
#     rain_playlist_url = requests.get("https://www.googleapis.com/youtube/v3/playlistItems?part=snippet&maxResults=50"
#                                         "&playlistId=" + playlist_id + "&fields=items%2Fsnippet(title)"
#                                         "&key=" + google_api_key)
#     rain_playlist_json = rain_playlist_url.json()
#     list_length = len(rain_playlist_json["items"])
#     #print(list_length)
#     song_title_list = []
#     for i in range(0, list_length):
#         rain_playlist_title = rain_playlist_json["items"][i]["snippet"]["title"]
#         song_title_list.append(rain_playlist_title)
#     return song_title_list


# Playlist IDs for the various Wx types:
playlist_ids = {
    "cloud": "PLyfbZoo34M08uXIE3QNSjudDvcJGIOSch",
    "sun": "PLyfbZoo34M09Nwe1TVaikLWuvUk7-8TCT",
    "rain": "PLyfbZoo34M08Xc3bbWIEN8tGnMTVkmjer",
    "snow": "PLyfbZoo34M09fAKIDbgJFUdiV8cfWG78f",
    "storm": "PLyfbZoo34M0_q-Ru5PayQit1vZbLahdNk",
}


# Processes the user save song request
@app.route("/save_song", methods=["POST"])
def save_song():
    if request.method == "POST":
        song_name = request.form["save_song"]
        song_url = request.form["save_url"]
        user = flask_login.current_user.get_id()
        #print(song_name, song_url, user)
        if SongList.query.filter_by(user_id=user, song_name=song_name).all():
            return jsonify({"song_status": "already saved"})
        else:
            song_info = SongList(song_name=song_name, song_url=song_url, user_id=user)
            db.session.add(song_info)
            db.session.commit()
            return jsonify({"song_status": "saved"})

    else:
        return redirect("/")


# This app was to be used to check if the current playing song was already saved in the db.
# @app.route("/song_check", methods=["POST"])
# def song_check():
#     if request.method == "POST":
#         song_name = request.form["save_check"]
#         print("MAYBE?")
#         user = flask_login.current_user.get_id()
#         if SongList.query.filter_by(user_id=user, song_name=song_name).all():
#             return jsonify({"song_status": "already saved"})
#         else:
#             return jsonify({"song_status": "save"})
#
#     else:
#         return redirect("/")


# These routes will be be another option to listen to the playlists, without location or weather being determined.
@app.route("/Cloud")
def cloud():
    return render_template("basic_playlist/only_cloud_playlist.html")


@app.route("/Sun")
def sun():
    return render_template("basic_playlist/only_sun_playlist.html")


@app.route("/Rain")
def rain():
    return render_template("basic_playlist/only_rain_playlist.html")


@app.route("/Snow")
def snow():
    return render_template("basic_playlist/only_snow_playlist.html")


@app.route("/Storm")
def storm():
    return render_template("basic_playlist/only_storm_playlist.html")


@app.route("/Profile", methods=["POST", "GET"])
@login_required
def profile():
    current_user_name = flask_login.current_user.username
    current_user_id = flask_login.current_user.get_id()
    user_songs = SongList.query.filter_by(user_id=current_user_id).all()

    if request.method == "POST":
        song_id = request.form["song_id"]
        print(song_id)
        delete_song = SongList.query.filter_by(user_id=current_user_id, id=song_id).first()
        db.session.delete(delete_song)
        db.session.commit()
        return redirect("Profile")
    else:
        return render_template("profile.html", current_user_name=current_user_name, user_songs=user_songs)


@app.route("/signup", methods=["POST", "GET"])
def signup():
    form = SignupForm()
    if form.validate_on_submit():
        new_user_username = request.form["username"]
        new_user_password = request.form["password"]

        try:
            new_user = User(username=new_user_username, password=new_user_password)
            db.session.add(new_user)
            db.session.commit()
            return redirect("/")
        except:
            flask.flash("There was an issue creating your account. Try a different username.")
            return redirect("signup")

    else:
        return render_template("authentication/signup.html", form=form)


@app.route("/login", methods=["POST", "GET"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        username = request.form["username"]
        password = request.form["password"]

        user = User.query.filter_by(username=username).first()

        if not user or not user.password == password:
            flask.flash("Looks like your login details were incorrect, please try again.")
            return redirect("/login")

        login_user(user)
        return redirect("/")
    return render_template("authentication/login.html", form=form)


@app.route("/logout")
def logout():
    logout_user()
    return render_template("authentication/logout.html")


if __name__ == "__main__":
    app.run(debug=True, port=8000)
