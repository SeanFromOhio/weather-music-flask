from flask import Flask, render_template, url_for, request, redirect
from flask_sqlalchemy import SQLAlchemy
import requests

app = Flask(__name__)
app.config["SQLAlchemy_DATABASE_URL"] = "sqlite:///"


@app.route("/", methods=['GET', 'POST'])
def index():
    if request.method == "POST":
        # Form accessing user location using HTML5 Geolocation API
        user_lat = request.form["hidden_lat"]
        user_long = request.form["hidden_long"]
        user_coords = user_lat + "," + user_long
        #print(user_coords)

        # User user coordinates to access National Weather Service (NWS) API
        # First, must find closest weather observation station using the following url:
        NWS_stations_url = ("https://api.weather.gov/points/" + user_coords + "/stations")
        #print(NWS_stations_url)

        # Next, read the JSON data and access key/value pair that houses our specific weather station data
        station_data = requests.get(NWS_stations_url)  # requests library not to be mistaken for flask-request
        station_data_json = station_data.json()  # Houses our needed data

        # Access the json data and grabs the needed url with the necessary page added on
        wx_observ_url = station_data_json["features"][0]["id"] + "/observations/latest"
        #print(wx_observ_url)

        # Now we have all the wx data from the closest observation station
        wx_data = requests.get(wx_observ_url)
        wx_data_json = wx_data.json()

        # Grab the specific weather text description, could be multiple elements.
        wx_text_description = wx_data_json["properties"]["textDescription"]
        print(wx_text_description)
        wx_type = None

        if "Cloud" in wx_text_description:
            print("Cloud")
            wx_type = "Cloud"
            return redirect("Cloud")
        elif "Sunny" or "Fair" or "Clear" in wx_text_description:
            print("Sun")
            wx_type = "Sun"
        elif "Snow" or "Freezing Rain" or "Sleet" in wx_text_description:
            print("Snow")
            wx_type = "Snow"
        elif "Rain" in wx_text_description:
            print("Rain")
            wx_type = "Rain"
        elif "Thunderstorm" or "Storm" in wx_text_description:
            print("Storm")
            wx_type = "Storm"

        return render_template("index.html", wx_type=wx_type)
    else:
        return render_template("index.html")


@app.route("/Cloud")
def cloud():
    return render_template("cloud.html")


@app.route("/Sun")
def sun():
    return render_template("sun.html")


@app.route("/Rain")
def rain():
    return render_template("rain.html")


@app.route("/Snow")
def snow():
    return render_template("snow.html")


@app.route("/Storm")
def storm():
    return render_template("storm.html")


if __name__ == "__main__":
    app.run(debug=True)
