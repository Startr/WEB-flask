from flask import Flask, render_template, request
from werkzeug.utils import secure_filename
import csv
import os
import re

app = Flask(__name__, static_url_path='')

# Create uploads directory if it doesn't exist
if not os.path.exists('uploads'):
    os.makedirs('uploads')

@app.route('/', methods=['GET'])
def show_form():
    return render_template('index.html')

@app.route('/', methods=['POST'])
def submit_form():
    name = request.form.get('name')
    email = request.form.get('email')
    cv = request.files.get('cv')  # Changed to use get method

    # Check if name and email are provided
    if not name or not email:
        return "Error: Name and Email are required", 400

    with open('contacts.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([name, email])

    if cv:
        filename = secure_filename(cv.filename)
        email_filename = re.sub(r'@', '_at_', email)
        cv_filename = f"{email_filename}.pdf"
        cv.save(os.path.join('uploads', cv_filename))

    return 'Thank you for submitting!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

