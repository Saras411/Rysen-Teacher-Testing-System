from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'rysen_secure_secret_key'
ADMIN_PASSWORD = "yourSecurePassword"  # change as you like


# In-memory data stores
questions_db = {
    'eduplay': {'junior': [], 'intermediate': [], 'advance': []},
    'cretile': {'junior': [], 'intermediate': [], 'advance': []},
    'pictoblocks': {'junior': [], 'intermediate': [], 'advance': []}
}
results_db = []
schools = ['Rysen Bikanagar', 'Rysen Bikaner', 'Rysen Deoli', 'Rysen Nimbhera']

# Key: (teacher_name, kit, level), Value: time in minutes
test_timings_db = {}


@app.route('/')
def index():
    return render_template('index.html', schools=schools)


@app.route('/admin_login', methods=['GET', 'POST'])
def admin_login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            return redirect(url_for('admin'))
        else:
            return render_template('admin_login.html', error="Invalid password")
    return render_template('admin_login.html')


@app.route('/admin_logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(url_for('admin_login'))


@app.route('/admin')
def admin():
    if not session.get('is_admin'):
        return redirect(url_for('admin_login'))
    return render_template('admin.html', questions=questions_db, results=results_db, schools=schools, timings=test_timings_db)


@app.route('/get_admin_data')
def get_admin_data():
    return jsonify({
        'questions': questions_db,
        'results': results_db,
        'schools': schools,
        'timings': test_timings_db
    })


@app.route('/start_test', methods=['POST'])
def start_test():
    data = request.json
    # Save teacher info and test info in session
    session['teacher_name'] = data['teacher_name']
    session['school'] = data['school']
    session['kit'] = data['kit']
    session['level'] = data['level']
    session['start_time'] = datetime.now().isoformat()

    questions = questions_db.get(data['kit'], {}).get(data['level'], [])
    key = (data['teacher_name'], data['kit'], data['level'])
    default_time = 15
    test_time = test_timings_db.get(key, default_time)

    return jsonify({
        'questions': questions,
        'total': len(questions),
        'test_time': test_time
    })


@app.route('/submit_test', methods=['POST'])
def submit_test():
    data = request.json
    answers = data.get('answers', [])

    questions = questions_db.get(session.get('kit'), {}).get(session.get('level'), [])
    score = 0
    total = len(questions)

    for i, answer in enumerate(answers):
        if i < total and answer == questions[i].get('correct_answer'):
            score += 1

    percentage = (score / total) * 100 if total > 0 else 0.0

    result = {
        'id': len(results_db) + 1,
        'teacher_name': session.get('teacher_name'),
        'school': session.get('school'),
        'kit': session.get('kit'),
        'level': session.get('level'),
        'score': score,
        'total': total,
        'percentage': round(percentage, 2),
        'date': datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        'answers': answers
    }
    results_db.append(result)

    return jsonify({
        'score': score,
        'total': total,
        'percentage': round(percentage, 2),
        'result_id': result['id']
    })


@app.route('/add_question', methods=['POST'])
def add_question():
    data = request.json
    question_list = questions_db.get(data['kit'], {}).get(data['level'], [])
    new_id = len(question_list) + 1
    question = {
        'id': new_id,
        'question': data['question'],
        'options': data['options'],
        'correct_answer': data['correct_answer']
    }
    question_list.append(question)
    return jsonify({'success': True, 'message': 'Question added successfully.'})


@app.route('/delete_question', methods=['POST'])
def delete_question():
    data = request.json
    qlist = questions_db.get(data['kit'], {}).get(data['level'], [])
    questions_db[data['kit']][data['level']] = [q for q in qlist if q['id'] != data['question_id']]
    return jsonify({'success': True, 'message': 'Question deleted successfully.'})


@app.route('/set_timing', methods=['POST'])
def set_timing():
    data = request.json
    key = (data['teacher_name'], data['kit'], data['level'])
    minutes = int(data['minutes'])
    test_timings_db[key] = minutes
    return jsonify({'success': True, 'message': 'Timing set successfully.'})


@app.route('/get_leaderboard')
def get_leaderboard():
    top_results = sorted(results_db, key=lambda r: r['percentage'], reverse=True)[:50]
    # Only teacher_name, no student_name
    leaderboard = [{
        'teacher_name': r['teacher_name'],
        'school': r['school'],
        'kit': r['kit'],
        'level': r['level'],
        'score': r['score'],
        'total': r['total'],
        'percentage': r['percentage'],
        'date': r['date']
    } for r in top_results]
    return jsonify(leaderboard)


@app.route('/get_analysis')
def get_analysis():
    if not results_db:
        return jsonify({
            'total_tests': 0,
            'average_score': 0,
            'school_performance': {},
            'kit_performance': {},
            'level_performance': {}
        })

    total_tests = len(results_db)
    average_score = sum(r['percentage'] for r in results_db) / total_tests

    # School performance
    school_perf = {}
    for school in schools:
        school_results = [r for r in results_db if r['school'] == school]
        if school_results:
            avg = sum(r['percentage'] for r in school_results) / len(school_results)
            school_perf[school] = {'tests': len(school_results), 'average': avg}

    # Kit performance
    kit_perf = {}
    for kit in ['eduplay', 'cretile', 'pictoblocks']:
        kit_results = [r for r in results_db if r['kit'] == kit]
        if kit_results:
            avg = sum(r['percentage'] for r in kit_results) / len(kit_results)
            kit_perf[kit] = {'tests': len(kit_results), 'average': avg}

    # Level performance
    level_perf = {}
    for level in ['junior', 'intermediate', 'advance']:
        level_results = [r for r in results_db if r['level'] == level]
        if level_results:
            avg = sum(r['percentage'] for r in level_results) / len(level_results)
            level_perf[level] = {'tests': len(level_results), 'average': avg}

    return jsonify({
        'total_tests': total_tests,
        'average_score': round(average_score, 2),
        'school_performance': school_perf,
        'kit_performance': kit_perf,
        'level_performance': level_perf
    })


if __name__ == '__main__':
    app.run(debug=True, port=5000)
