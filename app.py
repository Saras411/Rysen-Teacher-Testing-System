from flask import Flask, render_template, request, jsonify, session, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import os

app = Flask(__name__)
app.secret_key = 'rysen_secure_secret_key'
ADMIN_PASSWORD = "yourSecurePassword"

# Configure SQLite database
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rysen.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# In-memory data stores
questions_db = {
    'eduplay': {'junior': [], 'intermediate': [], 'advance': []},
    'cretile': {'junior': [], 'intermediate': [], 'advance': []},
    'pictoblocks': {'junior': [], 'intermediate': [], 'advance': []}
}
results_db = []
schools = ['Rysen Ganaganagar', 'Rysen Bikaner', 'Rysen Deoli', 'Rysen Nimbhera']



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
    # Fetch questions and results for display
    all_questions = Question.query.all()
    all_results = Result.query.order_by(Result.id.desc()).all()
    all_timings = TestTiming.query.all()
    return render_template(
        'admin.html',
        schools=schools,
        questions=all_questions,
        results=all_results,
        timings=all_timings
    )

@app.route('/get_admin_data')
def get_admin_data():
    questions = [
        {
            'id': q.id,
            'kit': q.kit,
            'level': q.level,
            'question': q.question,
            'options': q.options,
            'correct_answer': q.correct_answer
        } for q in Question.query.all()
    ]
    results = [
        {
            'id': r.id,
            'teacher_name': r.teacher_name,
            'school': r.school,
            'kit': r.kit,
            'level': r.level,
            'score': r.score,
            'total': r.total,
            'percentage': r.percentage,
            'date': r.date,
            'answers': r.answers
        } for r in Result.query.all()
    ]
    timings = [
        {
            'teacher_name': t.teacher_name,
            'kit': t.kit,
            'level': t.level,
            'minutes': t.minutes
        } for t in TestTiming.query.all()
    ]
    return jsonify({
        'questions': questions,
        'results': results,
        'schools': schools,
        'timings': timings
    })

@app.route('/start_test', methods=['POST'])
def start_test():
    data = request.json
    session['teacher_name'] = data['teacher_name']
    session['school'] = data['school']
    session['kit'] = data['kit']
    session['level'] = data['level']
    session['start_time'] = datetime.now().isoformat()

    questions = Question.query.filter_by(kit=data['kit'], level=data['level']).all()
    test_time = 15  # Default
    # Find timing for this teacher/kit/level
    timing = TestTiming.query.filter_by(
        teacher_name=data['teacher_name'],
        kit=data['kit'],
        level=data['level']
    ).first()
    if timing:
        test_time = timing.minutes

    serialized_questions = [
        {
            'id': q.id,
            'question': q.question,
            'options': q.options,
            'correct_answer': None   # Do not send answer key to frontend
        } for q in questions
    ]
    return jsonify({
        'questions': serialized_questions,
        'total': len(serialized_questions),
        'test_time': test_time
    })

@app.route('/submit_test', methods=['POST'])
def submit_test():
    data = request.json
    answers = data.get('answers', [])
    kit = session.get('kit')
    level = session.get('level')
    questions = Question.query.filter_by(kit=kit, level=level).all()
    score = 0
    total = len(questions)
    for i, answer in enumerate(answers):
        if i < total and answer == questions[i].correct_answer:
            score += 1
    percentage = (score / total) * 100 if total > 0 else 0.0
    result = Result(
        teacher_name=session.get('teacher_name'),
        school=session.get('school'),
        kit=kit,
        level=level,
        score=score,
        total=total,
        percentage=round(percentage, 2),
        date=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        answers=answers
    )
    db.session.add(result)
    db.session.commit()
    return jsonify({
        'score': score,
        'total': total,
        'percentage': round(percentage, 2),
        'result_id': result.id
    })

@app.route('/add_question', methods=['POST'])
def add_question():
    data = request.json
    q = Question(
        kit=data['kit'],
        level=data['level'],
        question=data['question'],
        options=data['options'],
        correct_answer=data['correct_answer']
    )
    db.session.add(q)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Question added successfully.'})

@app.route('/delete_question', methods=['POST'])
def delete_question():
    data = request.json
    q = Question.query.get(data['question_id'])
    if q:
        db.session.delete(q)
        db.session.commit()
        return jsonify({'success': True, 'message': 'Question deleted.'})
    return jsonify({'success': False, 'message': 'Question not found.'})

@app.route('/reset_questions', methods=['POST'])
def reset_questions():
    kit = request.form.get('kit')
    level = request.form.get('level')
    if kit and level:
        Question.query.filter_by(kit=kit, level=level).delete()
        db.session.commit()
        return jsonify({'success': True, 'message': 'Questions cleared.'})
    return jsonify({'success': False, 'message': 'Please provide kit and level.'})

@app.route('/set_timing', methods=['POST'])
def set_timing():
    data = request.json
    timing = TestTiming.query.filter_by(
        teacher_name=data['teacher_name'],
        kit=data['kit'],
        level=data['level']
    ).first()
    if timing:
        timing.minutes = int(data['minutes'])
    else:
        timing = TestTiming(
            teacher_name=data['teacher_name'],
            kit=data['kit'],
            level=data['level'],
            minutes=int(data['minutes'])
        )
        db.session.add(timing)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Timing set.'})

@app.route('/reset_leaderboard', methods=['POST'])
def reset_leaderboard():
    Result.query.delete()
    db.session.commit()
    return jsonify({'success': True, 'message': 'Leaderboard cleared.'})

@app.route('/get_leaderboard')
def get_leaderboard():
    results = Result.query.order_by(Result.percentage.desc()).limit(50).all()
    leaderboard = [{
        'teacher_name': r.teacher_name,
        'school': r.school,
        'kit': r.kit,
        'level': r.level,
        'score': r.score,
        'total': r.total,
        'percentage': r.percentage,
        'date': r.date
    } for r in results]
    return jsonify(leaderboard)

@app.route('/get_analysis')
def get_analysis():
    results = Result.query.all()
    if not results:
        return jsonify({
            'total_tests': 0,
            'average_score': 0,
            'school_performance': {},
            'kit_performance': {},
            'level_performance': {}
        })
    total_tests = len(results)
    average_score = sum(r.percentage for r in results) / total_tests
    # School performance
    school_perf = {}
    for school in schools:
        school_results = [r for r in results if r.school == school]
        if school_results:
            avg = sum(r.percentage for r in school_results) / len(school_results)
            school_perf[school] = {'tests': len(school_results), 'average': avg}
    # Kit performance
    kit_perf = {}
    for kit in ['eduplay', 'cretile', 'pictoblocks']:
        kit_results = [r for r in results if r.kit == kit]
        if kit_results:
            avg = sum(r.percentage for r in kit_results) / len(kit_results)
            kit_perf[kit] = {'tests': len(kit_results), 'average': avg}
    # Level performance
    level_perf = {}
    for level in ['junior', 'intermediate', 'advance']:
        level_results = [r for r in results if r.level == level]
        if level_results:
            avg = sum(r.percentage for r in level_results) / len(level_results)
            level_perf[level] = {'tests': len(level_results), 'average': avg}
    return jsonify({
        'total_tests': total_tests,
        'average_score': round(average_score, 2),
        'school_performance': school_perf,
        'kit_performance': kit_perf,
        'level_performance': level_perf
    })

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run(debug=True, port=5000)

