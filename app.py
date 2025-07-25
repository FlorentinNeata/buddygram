from flask import Flask, render_template, request, redirect, url_for, session, send_file
import mysql.connector
import os
import shutil

app = Flask(__name__)
app.secret_key = 'your_secret_key'

DATABASE_CONFIG = {
    'host': 'localhost',
    'user': 'root',
    'password': 'qwertyuiop',
    'database': 'poze'
}


UPLOAD_FOLDER = 'static/uploads'
if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

def get_db_connection():
    return mysql.connector.connect(**DATABASE_CONFIG)

@app.route('/')
def index():
    return send_file("index.html")
@app.route('/submit-login', methods=['POST'])
def submit_login():
    name = request.form.get('name')
    unique_code = request.form.get('unique_code')

    if not name or not unique_code:
        return 'Missing login details', 400

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT id, name, unique_code FROM users WHERE name = %s AND unique_code = %s", (name, unique_code))
        user = cursor.fetchone()

        if user:
            session['user_id'] = user[0]
            session['name'] = user[1]
            return redirect(url_for('main_page'))
        else:
            return 'Login Failed'
    finally:
        cursor.close()
        conn.close()

@app.route('/main')
def main_page():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    name = session.get('name')

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM ideas WHERE user_id = %s", (user_id,))
        idea_proposed = cursor.fetchone()[0] > 0

        cursor.execute("SELECT COUNT(*) FROM idea_votes WHERE user_id = %s", (user_id,))
        idea_voted = cursor.fetchone()[0] > 0

        cursor.execute("SELECT COUNT(*) FROM photos WHERE user_id = %s", (user_id,))
        photo_uploaded = cursor.fetchone()[0] > 0

        cursor.execute('''
            SELECT idea, COUNT(idea_votes.id) as vote_count
            FROM ideas
            LEFT JOIN idea_votes ON ideas.id = idea_votes.idea_id
            GROUP BY ideas.id
            ORDER BY vote_count DESC
            LIMIT 1
        ''')
        most_voted_idea = cursor.fetchone()

        cursor.execute('''
            SELECT users.name, COUNT(DISTINCT photo_votes.id) as vote_count
            FROM users
            LEFT JOIN photos ON users.id = photos.user_id
            LEFT JOIN photo_votes ON photos.id = photo_votes.photo_id
            GROUP BY users.id, users.name
            ORDER BY vote_count DESC
        ''')
        leaderboard_data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('success.html', name=name, idea_proposed=idea_proposed, idea_voted=idea_voted, photo_uploaded=photo_uploaded, most_voted_idea=most_voted_idea, leaderboard_data=leaderboard_data)


@app.route('/propose-idea', methods=['GET', 'POST'])
def propose_idea():
    if request.method == 'POST':
        idea = request.form.get('idea')
        user_id = session.get('user_id')
        if not user_id:
            return redirect(url_for('index'))

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO ideas (user_id, idea) VALUES (%s, %s)", (user_id, idea))
            conn.commit()
        finally:
            cursor.close()
            conn.close()

        return redirect(url_for('main_page'))

    return render_template('propose_idea.html')

@app.route('/vote-idea', methods=['GET', 'POST'])
def vote_idea():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        if request.method == 'POST':
            idea_id = request.form.get('idea_id')
            cursor.execute("INSERT INTO idea_votes (user_id, idea_id) VALUES (%s, %s)", (user_id, idea_id))
            conn.commit()
            return redirect(url_for('main_page'))

        cursor.execute("SELECT id, idea FROM ideas")
        ideas = cursor.fetchall()

        cursor.execute("SELECT COUNT(*) FROM idea_votes WHERE user_id = %s", (user_id,))
        idea_voted = cursor.fetchone()[0] > 0
    finally:
        cursor.close()
        conn.close()

    return render_template('vote_idea.html', ideas=ideas, idea_voted=idea_voted)

@app.route('/upload-photo', methods=['GET', 'POST'])
def upload_photo():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    if request.method == 'POST':
        if 'photo' not in request.files:
            return 'No file part'
        file = request.files['photo']
        if file.filename == '':
            return 'No selected file'
        if file:
            filename = file.filename
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                cursor.execute("INSERT INTO photos (user_id, filename) VALUES (%s, %s)", (user_id, filename))
                conn.commit()
            finally:
                cursor.close()
                conn.close()

            return redirect(url_for('main_page'))

    return render_template('upload_photo.html')

@app.route('/vote-photo', methods=['GET', 'POST'])
def vote_photo():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute("SELECT COUNT(*) FROM photo_votes WHERE user_id = %s", (user_id,))
        has_voted = cursor.fetchone()[0] > 0

        if request.method == 'POST' and not has_voted:
            photo_id = request.form.get('photo_id')
            cursor.execute("INSERT INTO photo_votes (user_id, photo_id) VALUES (%s, %s)", (user_id, photo_id))
            conn.commit()
            return redirect(url_for('main_page'))

        cursor.execute("SELECT id, filename FROM photos")
        photos = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('vote_photo.html', photos=photos, has_voted=has_voted)

@app.route('/leaderboard')
def leaderboard():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        cursor.execute('''
            SELECT users.name, COUNT(photo_votes.id) as vote_count
            FROM users
            LEFT JOIN photos ON users.id = photos.user_id
            LEFT JOIN photo_votes ON photos.id = photo_votes.photo_id
            GROUP BY users.id
            ORDER BY vote_count DESC
        ''')
        leaderboard_data = cursor.fetchall()
    finally:
        cursor.close()
        conn.close()

    return render_template('leaderboard.html', leaderboard_data=leaderboard_data)

@app.route('/reset-app', methods=['POST'])
def reset_app():
    user_id = session.get('user_id')
    if not user_id:
        return redirect(url_for('index'))

    name = session.get('name')
    if name != 'Florentin':
        return redirect(url_for('main_page'))

    conn = get_db_connection()
    cursor = conn.cursor()

    try:
        # Delete all entries from the specified tables
        cursor.execute("DELETE FROM photo_votes")
        cursor.execute("DELETE FROM photos")
        cursor.execute("DELETE FROM idea_votes")
        cursor.execute("DELETE FROM ideas")
        conn.commit()

        # Clear the upload folder
        folder = app.config['UPLOAD_FOLDER']
        for filename in os.listdir(folder):
            file_path = os.path.join(folder, filename)
            if os.path.isfile(file_path) or os.path.islink(file_path):
                os.unlink(file_path)
            elif os.path.isdir(file_path):
                shutil.rmtree(file_path)
    finally:
        cursor.close()
        conn.close()

    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True)
