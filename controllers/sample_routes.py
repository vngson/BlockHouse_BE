from flask import Blueprint, jsonify

sample_bp = Blueprint('sample', __name__)

@sample_bp.route('/users')
def users():
    return jsonify({"message": "List of users"})

@sample_bp.route('/houses')
def houses():
    return jsonify({"message": "List of houses"})

@sample_bp.route('/bookings')
def bookings():
    return jsonify({"message": "List of bookings"})