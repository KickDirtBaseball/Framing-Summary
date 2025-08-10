from flask import Flask, jsonify, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

@app.route('/api/catchers')
def get_catchers():
    return jsonify([{
        "id": 1,
        "player_name": "Test Catcher",
        "team": "LAD",
        "called_strike_rate": 0.65,
        "extra_strikes": 2,
        "lost_strikes": 1
    }])

if __name__ == '__main__':
    app.run(debug=True, port=5000)
    