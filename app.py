from flask import Flask, render_template, request
import csv

app = Flask(__name__, static_folder='static')

# Define the route for the home page
@app.route('/', methods=['GET'])
def show_form():
    return render_template('index.html')

# Define the route for form submission
@app.route('/', methods=['POST'])
def submit_form():
    # Retrieve the form data
    name = request.form.get('name')
    email = request.form.get('email')

    # Save the contact information to a CSV file
    with open('contacts.csv', 'a', newline='') as file:
        writer = csv.writer(file)
        writer.writerow([name, email])

    return 'Thank you for submitting!'

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)

