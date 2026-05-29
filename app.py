from flask import Flask, render_template, request, redirect, url_for, session, jsonify, flash, send_from_directory
import sqlite3
import hashlib
from datetime import datetime, timedelta
import os
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = 'blender3d_secret_key_2026'
DATABASE = 'database.db'
UPLOAD_FOLDER = 'uploads'

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

def get_db():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

def get_unread_count():
    if 'student_id' in session and session.get('user_type') == 'student':
        conn = get_db()
        count = conn.execute("SELECT COUNT(*) FROM notifications WHERE student_id = ? AND is_read = 0", (session['student_id'],)).fetchone()[0]
        conn.close()
        return count
    return 0

@app.context_processor
def inject_nav_data():
    data = {}
    if 'student_id' in session and session.get('user_type') == 'student':
        data['unread_count'] = get_unread_count()
    else:
        data['unread_count'] = 0
    return data

def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS teachers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            phone TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS classes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            teacher_id INTEGER NOT NULL,
            class_name TEXT NOT NULL,
            class_code TEXT UNIQUE NOT NULL,
            class_password TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (teacher_id) REFERENCES teachers(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            full_name TEXT NOT NULL,
            class_id INTEGER NOT NULL,
            class_password TEXT NOT NULL,
            password TEXT NOT NULL,
            xp INTEGER DEFAULT 0,
            level INTEGER DEFAULT 1,
            total_score INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (class_id) REFERENCES classes(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS topics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            description TEXT,
            video_url TEXT,
            theory TEXT,
            practical_guide TEXT,
            order_num INTEGER DEFAULT 0
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS practical_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            project_num INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            steps TEXT,
            criteria TEXT,
            order_num INTEGER DEFAULT 0,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS tasks (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            topic_id INTEGER NOT NULL,
            task_type TEXT NOT NULL,
            question TEXT NOT NULL,
            options TEXT,
            correct_answer TEXT,
            points INTEGER DEFAULT 10,
            order_num INTEGER DEFAULT 0,
            FOREIGN KEY (topic_id) REFERENCES topics(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS student_progress (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            task_id INTEGER NOT NULL,
            completed INTEGER DEFAULT 0,
            score INTEGER DEFAULT 0,
            completed_at TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS badges (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            badge_name TEXT NOT NULL,
            badge_icon TEXT,
            earned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS chat_messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            user_type TEXT NOT NULL,
            message TEXT NOT NULL,
            response TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS project_submissions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            topic_id INTEGER NOT NULL,
            filename TEXT NOT NULL,
            filepath TEXT NOT NULL,
            file_format TEXT DEFAULT 'blend',
            submitted_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            teacher_score INTEGER DEFAULT NULL,
            teacher_comment TEXT DEFAULT NULL,
            graded_at TIMESTAMP DEFAULT NULL,
            status TEXT DEFAULT 'pending',
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (project_id) REFERENCES practical_projects(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            message TEXT NOT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)
    c.execute("""
        CREATE TABLE IF NOT EXISTS certificates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            certificate_code TEXT UNIQUE NOT NULL,
            generated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id)
        )
    """)
    c.execute("SELECT COUNT(*) FROM topics")
    if c.fetchone()[0] == 0:
        topics_data = [
            ("§1. Интерфейс және негізгі құралдар", "Blender бағдарламасының интерфейсімен танысу", "https://youtu.be/GVy2Gpi81rU",
             "Blender — ашық бастапқы коды бар 3D компьютерлік графика бағдарламасы. Ол 3D модельдеу, анимация, рендеринг, видео монтаж және т.б. мүмкіндіктерді қамтиды.",
             "1-практикалық жоба. Жұмыс үстелін модельдеу", 1),
            ("§2. Модель құру: бөлшектерді біріктіру және тегістеу", "Модель құрудың негізгі тәсілдері", "https://youtu.be/zgoEzNNP_Iw",
             "3D модельдеуде объектілерді құрудың бірнеше тәсілі бар: экструдия (E), инсерт (I), булеан операциялары.",
             "2,3,4-практикалық жобалар", 2),
            ("§3. Материалдар және текстуралар", "Материалдар мен текстураларды таңдау", "https://youtu.be/vUHGGM-TdPI",
             "Материалдар объектінің сыртқы түрін анықтайды. Blender-де Principled BSDF шейдері қолданылады.",
             "5-практикалық жоба. Материал мен текстура таңдау", 3),
            ("§4. Жарық және камера", "Жарық пен камераны орнату", "https://youtu.be/6BDdcsqGoJw",
             "3D сценада жарық көздері маңызды рөл атқарады.",
             "6-практикалық жоба. Жарық пен камераны орнату", 4),
            ("§5. Рендеринг: фотореалистік визуализациялау", "Рендеринг процесі", "https://youtu.be/Q6jHF9vRfnQ",
             "Рендеринг — 3D сценаны 2D суретке айналдыру процесі.",
             "7-практикалық жоба. Рендеринг", 5),
            ("§6. Анимациямен жұмыс", "Анимация жасау негіздері", "https://youtu.be/0K4h5ECs8xQ",
             "Анимация — объектілердің уақыт бойынша өзгерісі.",
             "8-практикалық жоба. Анимация жасау", 6),
            ("§7. Менің 3D жобам", "Өз 3D жобасын жасау", "https://youtu.be/lAjVHGWK3ss",
             "Жобалық жұмыс — бұл оқушының өзі жасаған 3D моделі.",
             "9,10-практикалық жобалар", 7),
        ]
        c.executemany("INSERT INTO topics (title, description, video_url, theory, practical_guide, order_num) VALUES (?,?,?,?,?,?)", topics_data)
    c.execute("SELECT COUNT(*) FROM practical_projects")
    if c.fetchone()[0] == 0:
        projects_data = [
            (1, 1, "1-практикалық жоба. Жұмыс үстелін модельдеу", "Жұмыс үстелінің 3D моделін жасау.", "1. Blender ашыңыз|2. Объектілерді қосыңыз|3. Рендер жасаңыз", "Модель (2)|Материал (2)|Жарық (2)|Камера (2)|Көркемдік (2)", 1),
            (2, 2, "2-практикалық жоба. Модель құру", "Базалық объектілерді қолдану.", "1. Объект таңдаңыз|2. Modifier қолданыңыз|3. Edit Mode|4. Рендер", "Модель (2)|Modifier (2)|Тегістік (2)|Деталь (2)|Көркемдік (2)", 1),
            (2, 3, "3-практикалық жоба. Бөлшектерді біріктіру", "Boolean операциялары.", "1. Екі объекті|2. Boolean|3. Union/Difference|4. Рендер", "Біріктіру (2)|Пішін (2)|Материал (2)|Жарық (2)|Рендер (2)", 2),
            (2, 4, "4-практикалық жоба. Объект бетін тегістеу", "Subdivision Surface.", "1. Объект таңдаңыз|2. Subdivision|3. Smooth Shading|4. Рендер", "Тегістік (2)|Subdivision (2)|Пішін (2)|Материал (2)|Рендер (2)", 3),
            (3, 5, "5-практикалық жоба. Материал мен текстура", "Principled BSDF.", "1. Shader Editor|2. BSDF|3. UV Mapping|4. Рендер", "Материал (2)|Текстура (2)|UV (2)|Жарық (2)|Рендер (2)", 1),
            (4, 6, "6-практикалық жоба. Жарық пен камера", "Three-point lighting.", "1. Жарық қосыңыз|2. Key/Fill/Back|3. Камера|4. Рендер", "Жарық (2)|Камера (2)|DOF (2)|Түс (2)|Рендер (2)", 1),
            (5, 7, "7-практикалық жоба. Рендеринг", "Cycles/Eevee.", "1. Қозғалтқыш|2. Сэмпл|3. Өлшем|4. Рендер", "Сапа (2)|Сэмпл (2)|Денойзинг (2)|Өлшем (2)|Уақыт (2)", 1),
            (6, 8, "8-практикалық жоба. Анимация", "Keyframe.", "1. Timeline|2. Keyframe|3. Graph Editor|4. Render Animation", "Плавность (2)|Keyframe (2)|Graph (2)|Рендер (2)|Уақыт (2)", 1),
            (7, 9, "9-практикалық жоба. 3D жоба", "Өз жобаңыз.", "1. Тақырып|2. Жоспар|3. Модель|4. Материал|5. Рендер", "Тақырып (2)|Модель (2)|Материал (2)|Жарық (2)|Рендер (2)", 1),
            (7, 10, "10-практикалық жоба. Презентация", "Жобаны қорғау.", "1. 5 сурет|2. Презентация|3. Сипаттама|4. Қорғау", "Құрылым (2)|Сурет (2)|Сипаттама (2)|Техника (2)|Қорғау (2)", 2),
        ]
        c.executemany("INSERT INTO practical_projects (topic_id, project_num, title, description, steps, criteria, order_num) VALUES (?,?,?,?,?,?,?)", projects_data)
    c.execute("SELECT COUNT(*) FROM tasks")
    if c.fetchone()[0] == 0:
        tasks_data = [
            (1, "multiple_choice", "Blender негізгі панелі?", "3D Viewport|Outliner|Properties|Timeline", "3D Viewport", 10, 1),
            (1, "fill_blank", "Объектілерді қозғалту үшін ___ пернесі.", None, "G", 10, 2),
            (1, "matching", "Сәйкестендіріңіз", "G:қозғалту|S:масштабтау|R:айналдыру", "G:қозғалту|S:масштабтау|R:айналдыру", 15, 3),
            (2, "multiple_choice", "Boolean не істейді?", "Біріктіру|Тегістеу|Айналдыру|Көшіру", "Біріктіру", 10, 1),
            (2, "fill_blank", "Экструдия ___ перне.", None, "E", 10, 2),
            (3, "multiple_choice", "BSDF негізгі параметрі?", "Base Color|Alpha|Normal|Displacement", "Base Color", 10, 1),
            (4, "multiple_choice", "Барлық бағытта жарық?", "Point|Sun|Spot|Area", "Point", 10, 1),
            (5, "multiple_choice", "Фотореалистік рендер?", "Eevee|Cycles|Workbench", "Cycles", 10, 1),
            (6, "multiple_choice", "Анимация негізі?", "Keyframe|Modifier|Shader", "Keyframe", 10, 1),
            (7, "multiple_choice", "Презентация неше сурет?", "1|3|5|10", "5", 10, 1),
        ]
        c.executemany("INSERT INTO tasks (topic_id, task_type, question, options, correct_answer, points, order_num) VALUES (?,?,?,?,?,?,?)", tasks_data)
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    conn = get_db()
    teachers_count = conn.execute("SELECT COUNT(*) FROM teachers").fetchone()[0]
    students_count = conn.execute("SELECT COUNT(*) FROM students").fetchone()[0]
    topics = conn.execute("SELECT * FROM topics ORDER BY order_num").fetchall()
    conn.close()
    return render_template('index.html', teachers_count=teachers_count, students_count=students_count, total_count=teachers_count + students_count, topics=topics)

@app.route('/register_teacher', methods=['GET', 'POST'])
def register_teacher():
    if request.method == 'POST':
        full_name = request.form['full_name']
        phone = request.form['phone']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        try:
            conn.execute("INSERT INTO teachers (full_name, phone, password) VALUES (?, ?, ?)", (full_name, phone, hashed))
            conn.commit()
            flash('Мұғалім сәтті тіркелді!', 'success')
            return redirect(url_for('login_teacher'))
        except sqlite3.IntegrityError:
            flash('Бұл телефон бұрын тіркелген!', 'error')
        finally:
            conn.close()
    return render_template('register_teacher.html')

@app.route('/login_teacher', methods=['GET', 'POST'])
def login_teacher():
    if request.method == 'POST':
        phone = request.form['phone']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        teacher = conn.execute("SELECT * FROM teachers WHERE phone = ? AND password = ?", (phone, hashed)).fetchone()
        conn.close()
        if teacher:
            session['teacher_id'] = teacher['id']
            session['teacher_name'] = teacher['full_name']
            session['user_type'] = 'teacher'
            return redirect(url_for('teacher_dashboard'))
        else:
            flash('Телефон немесе пароль қате!', 'error')
    return render_template('login_teacher.html')

@app.route('/teacher_dashboard')
def teacher_dashboard():
    if 'teacher_id' not in session or session.get('user_type') != 'teacher':
        return redirect(url_for('login_teacher'))
    conn = get_db()
    classes = conn.execute("SELECT * FROM classes WHERE teacher_id = ?", (session['teacher_id'],)).fetchall()
    students_stats = []
    all_submissions = []
    for cls in classes:
        students = conn.execute("SELECT * FROM students WHERE class_id = ?", (cls['id'],)).fetchall()
        total_xp = sum(s['xp'] for s in students) if students else 0
        avg_progress = 0
        if students:
            for s in students:
                progress = conn.execute("SELECT COUNT(*) as completed, (SELECT COUNT(*) FROM tasks) as total FROM student_progress WHERE student_id = ? AND completed = 1", (s['id'],)).fetchone()
                if progress['total'] > 0:
                    avg_progress += (progress['completed'] / progress['total']) * 100
            avg_progress = avg_progress / len(students) if students else 0
        students_stats.append({'class': cls, 'students': students, 'count': len(students), 'total_xp': total_xp, 'avg_progress': round(avg_progress, 1)})
        for s in students:
            subs = conn.execute("SELECT ps.*, pp.title as project_title, s.full_name FROM project_submissions ps JOIN practical_projects pp ON ps.project_id = pp.id JOIN students s ON ps.student_id = s.id WHERE ps.student_id = ? ORDER BY ps.submitted_at DESC", (s['id'],)).fetchall()
            all_submissions.extend(subs)
    conn.close()
    return render_template('teacher_dashboard.html', classes=classes, students_stats=students_stats, submissions=all_submissions)

@app.route('/create_class', methods=['POST'])
def create_class():
    if 'teacher_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    conn = get_db()
    try:
        conn.execute("INSERT INTO classes (teacher_id, class_name, class_code, class_password) VALUES (?, ?, ?, ?)", (session['teacher_id'], data.get('class_name'), data.get('class_code'), data.get('class_password')))
        conn.commit()
        return jsonify({'success': True})
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Бұл сынып коды бұрын қолданылған!'}), 400
    finally:
        conn.close()

@app.route('/grade_submission/<int:sub_id>', methods=['POST'])
def grade_submission(sub_id):
    if 'teacher_id' not in session or session.get('user_type') != 'teacher':
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    score = data.get('score')
    comment = data.get('comment', '')
    conn = get_db()
    sub = conn.execute("SELECT * FROM project_submissions WHERE id = ?", (sub_id,)).fetchone()
    if not sub:
        conn.close()
        return jsonify({'error': 'Жүктеме табылмады'}), 404
    conn.execute("UPDATE project_submissions SET teacher_score = ?, teacher_comment = ?, graded_at = ?, status = 'graded' WHERE id = ?", (score, comment, datetime.now(), sub_id))
    student_id = sub['student_id']
    total_task_score = conn.execute("SELECT COALESCE(SUM(score), 0) FROM student_progress WHERE student_id = ? AND completed = 1", (student_id,)).fetchone()[0]
    total_project_score = conn.execute("SELECT COALESCE(SUM(teacher_score), 0) FROM project_submissions WHERE student_id = ? AND status = 'graded'", (student_id,)).fetchone()[0]
    conn.execute("UPDATE students SET total_score = ? WHERE id = ?", (total_task_score + total_project_score, student_id))
    conn.execute("INSERT INTO notifications (student_id, title, message) VALUES (?, ?, ?)", (student_id, 'Практикалық жоба бағаланды', f'Мұғалім сіздің жобаңызды бағалады: {score}/10. Пікір: {comment}'))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/register_student', methods=['GET', 'POST'])
def register_student():
    if request.method == 'POST':
        full_name = request.form['full_name']
        class_code = request.form['class_code']
        class_password = request.form['class_password']
        password = request.form['password']
        conn = get_db()
        cls = conn.execute("SELECT * FROM classes WHERE class_code = ? AND class_password = ?", (class_code, class_password)).fetchone()
        if not cls:
            flash('Сынып коды немесе пароль қате!', 'error')
            conn.close()
            return render_template('register_student.html')
        hashed = hashlib.sha256(password.encode()).hexdigest()
        try:
            conn.execute("INSERT INTO students (full_name, class_id, class_password, password) VALUES (?, ?, ?, ?)", (full_name, cls['id'], class_password, hashed))
            conn.commit()
            flash('Оқушы сәтті тіркелді!', 'success')
            return redirect(url_for('login_student'))
        except Exception as e:
            flash('Тіркеу қатесі!', 'error')
        finally:
            conn.close()
    return render_template('register_student.html')

@app.route('/login_student', methods=['GET', 'POST'])
def login_student():
    if request.method == 'POST':
        full_name = request.form['full_name']
        class_code = request.form['class_code']
        class_password = request.form['class_password']
        password = request.form['password']
        hashed = hashlib.sha256(password.encode()).hexdigest()
        conn = get_db()
        student = conn.execute("SELECT s.*, c.class_name FROM students s JOIN classes c ON s.class_id = c.id WHERE s.full_name = ? AND c.class_code = ? AND s.class_password = ? AND s.password = ?", (full_name, class_code, class_password, hashed)).fetchone()
        conn.close()
        if student:
            session['student_id'] = student['id']
            session['student_name'] = student['full_name']
            session['class_id'] = student['class_id']
            session['user_type'] = 'student'
            return redirect(url_for('student_dashboard'))
        else:
            flash('Ақпарат қате!', 'error')
    return render_template('login_student.html')

@app.route('/student_dashboard')
def student_dashboard():
    if 'student_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('login_student'))
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (session['student_id'],)).fetchone()
    progress = conn.execute("SELECT COUNT(*) as completed, (SELECT COUNT(*) FROM tasks) as total FROM student_progress WHERE student_id = ? AND completed = 1", (session['student_id'],)).fetchone()
    progress_percent = (progress['completed'] / progress['total'] * 100) if progress['total'] > 0 else 0
    badges = conn.execute("SELECT * FROM badges WHERE student_id = ?", (session['student_id'],)).fetchall()
    leaderboard = conn.execute("SELECT s.full_name, s.xp, s.level, c.class_name FROM students s JOIN classes c ON s.class_id = c.id ORDER BY s.xp DESC LIMIT 10").fetchall()
    notifications = conn.execute("SELECT * FROM notifications WHERE student_id = ? ORDER BY created_at DESC LIMIT 10", (session['student_id'],)).fetchall()
    unread_count = conn.execute("SELECT COUNT(*) FROM notifications WHERE student_id = ? AND is_read = 0", (session['student_id'],)).fetchone()[0]
    topics = conn.execute("SELECT * FROM topics ORDER BY order_num").fetchall()
    submissions = conn.execute("SELECT ps.*, pp.title as project_title FROM project_submissions ps JOIN practical_projects pp ON ps.project_id = pp.id WHERE ps.student_id = ? ORDER BY ps.submitted_at DESC", (session['student_id'],)).fetchall()
    conn.close()
    return render_template('student_dashboard.html', student=student, progress=progress_percent, badges=badges, leaderboard=leaderboard, topics=topics, notifications=notifications, unread_count=unread_count, submissions=submissions)

@app.route('/topic/<int:topic_id>')
def topic_detail(topic_id):
    conn = get_db()
    topic = conn.execute("SELECT * FROM topics WHERE id = ?", (topic_id,)).fetchone()
    tasks = conn.execute("SELECT * FROM tasks WHERE topic_id = ? ORDER BY order_num", (topic_id,)).fetchall()
    projects = conn.execute("SELECT * FROM practical_projects WHERE topic_id = ? ORDER BY order_num", (topic_id,)).fetchall()
    task_progress = {}
    project_submissions = {}
    all_tasks_completed = False
    if 'student_id' in session and session.get('user_type') == 'student':
        for task in tasks:
            prog = conn.execute("SELECT * FROM student_progress WHERE student_id = ? AND task_id = ?", (session['student_id'], task['id'])).fetchone()
            task_progress[task['id']] = prog
        for project in projects:
            sub = conn.execute("SELECT * FROM project_submissions WHERE student_id = ? AND project_id = ?", (session['student_id'], project['id'])).fetchone()
            project_submissions[project['id']] = sub
        completed_count = conn.execute("SELECT COUNT(*) FROM student_progress WHERE student_id = ? AND task_id IN (SELECT id FROM tasks WHERE topic_id = ?) AND completed = 1", (session['student_id'], topic_id)).fetchone()[0]
        all_tasks_completed = completed_count >= len(tasks)
    conn.close()
    return render_template('topic.html', topic=topic, tasks=tasks, projects=projects, task_progress=task_progress, project_submissions=project_submissions, all_tasks_completed=all_tasks_completed)

@app.route('/project/<int:project_id>')
def project_detail(project_id):
    if 'student_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('login_student'))
    conn = get_db()
    project = conn.execute("SELECT * FROM practical_projects WHERE id = ?", (project_id,)).fetchone()
    topic = conn.execute("SELECT * FROM topics WHERE id = ?", (project['topic_id'],)).fetchone()
    submission = conn.execute("SELECT * FROM project_submissions WHERE student_id = ? AND project_id = ?", (session['student_id'], project_id)).fetchone()
    conn.close()
    if not project:
        flash('Жоба табылмады!', 'error')
        return redirect(url_for('student_dashboard'))
    return render_template('project.html', project=project, topic=topic, submission=submission)

# ===== ЕСКІ ЖҮКТЕУ (бұрынғыдай жұмыс істей береді) =====
@app.route('/upload_project/<int:project_id>', methods=['POST'])
def upload_project(project_id):
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    if 'file' not in request.files:
        return jsonify({'error': 'Файл табылмады'}), 400
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'Файл таңдалмады'}), 400
    conn = get_db()
    project = conn.execute("SELECT * FROM practical_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Жоба табылмады'}), 404
    topic_id = project['topic_id']
    conn.close()
    if file and file.filename.endswith('.blend'):
        filename = f"student_{session['student_id']}_project_{project_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.blend"
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        conn = get_db()
        conn.execute("DELETE FROM project_submissions WHERE student_id = ? AND project_id = ?", (session['student_id'], project_id))
        conn.execute("INSERT INTO project_submissions (student_id, project_id, topic_id, filename, filepath) VALUES (?, ?, ?, ?, ?)", (session['student_id'], project_id, topic_id, filename, filepath))
        conn.commit()
        conn.close()
        return jsonify({'success': True, 'message': 'Жоба сәтті жүктелді!'})
    return jsonify({'error': 'Тек .blend файлы жүктеуге рұқсат етіледі'}), 400

# ===== ЖАҢА: 3 ФОРМАТ БОЙЫНША ЖҮКТЕУ API =====
@app.route('/api/upload_project/<int:project_id>', methods=['POST'])
def upload_project_files(project_id):
    if 'student_id' not in session or session.get('user_type') != 'student':
        return jsonify({'error': 'Кіру қажет'}), 401
    conn = get_db()
    project = conn.execute("SELECT * FROM practical_projects WHERE id = ?", (project_id,)).fetchone()
    if not project:
        conn.close()
        return jsonify({'error': 'Жоба табылмады'}), 404
    topic_id = project['topic_id']
    student_id = session['student_id']
    saved_files = []
    errors = []
    for format_type in ['blend', 'pdf', 'pptx']:
        files = request.files.getlist(format_type + '_files[]')
        existing_count = conn.execute("SELECT COUNT(*) FROM project_submissions WHERE student_id = ? AND project_id = ? AND file_format = ?", (student_id, project_id, format_type)).fetchone()[0]
        for file in files:
            if not file or not file.filename:
                continue
            expected_ext = '.' + format_type
            if not file.filename.lower().endswith(expected_ext):
                errors.append(f'{file.filename}: Тек {expected_ext} форматы қабылданады')
                continue
            file.seek(0, os.SEEK_END)
            file_size = file.tell()
            file.seek(0)
            if file_size > 50 * 1024 * 1024:
                errors.append(f'{file.filename}: 50MB-тан аспауы керек')
                continue
            if existing_count >= 3:
                errors.append(f'{format_type.upper()}: 3 файлдан аспауы керек')
                break
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            original_name = secure_filename(file.filename)
            filename = f"student_{student_id}_project_{project_id}_{format_type}_{timestamp}_{original_name}"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            conn.execute("INSERT INTO project_submissions (student_id, project_id, topic_id, filename, filepath, file_format, status) VALUES (?, ?, ?, ?, ?, ?, 'pending')", (student_id, project_id, topic_id, original_name, filepath, format_type))
            saved_files.append({'filename': original_name, 'format': format_type, 'size': file_size})
            existing_count += 1
    conn.commit()
    conn.close()
    if saved_files:
        return jsonify({'success': True, 'message': f'{len(saved_files)} файл сәтті жүктелді!', 'files': saved_files, 'errors': errors if errors else None})
    else:
        return jsonify({'success': False, 'error': 'Ешқандай файл жүктелмеді', 'details': errors}), 400

@app.route('/api/delete_submission/<int:sub_id>', methods=['POST'])
def delete_submission(sub_id):
    if 'student_id' not in session or session.get('user_type') != 'student':
        return jsonify({'error': 'Кіру қажет'}), 401
    conn = get_db()
    sub = conn.execute("SELECT * FROM project_submissions WHERE id = ? AND student_id = ?", (sub_id, session['student_id'])).fetchone()
    if not sub:
        conn.close()
        return jsonify({'error': 'Жүктеме табылмады немесе рұқсат жоқ'}), 404
    if sub['filepath'] and os.path.exists(sub['filepath']):
        os.remove(sub['filepath'])
    conn.execute("DELETE FROM project_submissions WHERE id = ?", (sub_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Файл өшірілді'})

@app.route('/api/my_submissions/<int:project_id>')
def my_submissions(project_id):
    if 'student_id' not in session or session.get('user_type') != 'student':
        return jsonify({'error': 'Кіру қажет'}), 401
    conn = get_db()
    submissions = conn.execute("SELECT id, filename, file_format, status, teacher_score, teacher_comment, graded_at, submitted_at FROM project_submissions WHERE student_id = ? AND project_id = ? ORDER BY file_format, submitted_at DESC", (session['student_id'], project_id)).fetchall()
    conn.close()
    result = {'blend': [], 'pdf': [], 'pptx': []}
    for sub in submissions:
        fmt = sub['file_format']
        if fmt in result:
            result[fmt].append({'id': sub['id'], 'filename': sub['filename'], 'status': sub['status'], 'score': sub['teacher_score'], 'comment': sub['teacher_comment'], 'graded_at': sub['graded_at'], 'submitted_at': sub['submitted_at']})
    return jsonify({'success': True, 'submissions': result})

@app.route('/submit_task', methods=['POST'])
def submit_task():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    data = request.get_json()
    task_id = data.get('task_id')
    answer = data.get('answer')
    conn = get_db()
    task = conn.execute("SELECT * FROM tasks WHERE id = ?", (task_id,)).fetchone()
    if not task:
        conn.close()
        return jsonify({'error': 'Тапсырма табылмады'}), 404
    is_correct = False
    score = 0
    correct = task['correct_answer']
    if answer.strip().lower() == correct.strip().lower():
        is_correct = True
        score = task['points']
    existing = conn.execute("SELECT * FROM student_progress WHERE student_id = ? AND task_id = ?", (session['student_id'], task_id)).fetchone()
    if existing:
        conn.execute("UPDATE student_progress SET completed = ?, score = ?, completed_at = ? WHERE id = ?", (1 if is_correct else 0, score, datetime.now(), existing['id']))
    else:
        conn.execute("INSERT INTO student_progress (student_id, task_id, completed, score, completed_at) VALUES (?, ?, ?, ?, ?)", (session['student_id'], task_id, 1 if is_correct else 0, score, datetime.now()))
    if is_correct:
        conn.execute("UPDATE students SET xp = xp + ? WHERE id = ?", (score, session['student_id']))
        total_xp = conn.execute("SELECT xp FROM students WHERE id = ?", (session['student_id'],)).fetchone()['xp']
        new_level = (total_xp // 100) + 1
        conn.execute("UPDATE students SET level = ? WHERE id = ?", (new_level, session['student_id']))
        badges_to_check = [(50, 'Бастаушы', 'star'), (100, '3D модельдеуші', 'cube'), (200, 'Аниматор', 'film'), (300, 'Профессионал', 'trophy'), (500, '3D шебер', 'crown'), (750, 'Blender шебері', 'gem'), (1000, '3D Гуру', 'award')]
        for xp_needed, badge_name, badge_icon in badges_to_check:
            if total_xp >= xp_needed:
                existing_badge = conn.execute("SELECT * FROM badges WHERE student_id = ? AND badge_name = ?", (session['student_id'], badge_name)).fetchone()
                if not existing_badge:
                    conn.execute("INSERT INTO badges (student_id, badge_name, badge_icon) VALUES (?, ?, ?)", (session['student_id'], badge_name, badge_icon))
    conn.commit()
    conn.close()
    return jsonify({'correct': is_correct, 'score': score, 'message': 'Дұрыс! Керемет!' if is_correct else 'Қате! Дұрыс жауап: ' + task['correct_answer']})

@app.route('/download/<path:filename>')
def download_file(filename):
    if 'teacher_id' not in session and 'student_id' not in session:
        return redirect(url_for('index'))
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/my_grades')
def my_grades():
    if 'student_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('login_student'))
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (session['student_id'],)).fetchone()
    task_grades = conn.execute("SELECT t.question, t.task_type, sp.score, t.points, t.order_num, tp.title as topic_title FROM student_progress sp JOIN tasks t ON sp.task_id = t.id JOIN topics tp ON t.topic_id = tp.id WHERE sp.student_id = ? AND sp.completed = 1 ORDER BY tp.order_num, t.order_num", (session['student_id'],)).fetchall()
    project_grades = conn.execute("SELECT ps.*, pp.title as project_title FROM project_submissions ps JOIN practical_projects pp ON ps.project_id = pp.id WHERE ps.student_id = ? AND ps.status = 'graded' ORDER BY ps.graded_at DESC", (session['student_id'],)).fetchall()
    total_task_score = conn.execute("SELECT COALESCE(SUM(score), 0) FROM student_progress WHERE student_id = ? AND completed = 1", (session['student_id'],)).fetchone()[0]
    total_project_score = conn.execute("SELECT COALESCE(SUM(teacher_score), 0) FROM project_submissions WHERE student_id = ? AND status = 'graded'", (session['student_id'],)).fetchone()[0]
    total_score = total_task_score + total_project_score
    total_tasks = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    total_projects = conn.execute("SELECT COUNT(*) FROM practical_projects").fetchone()[0]
    max_possible = (total_tasks * 10) + (total_projects * 10)
    avg_percent = (total_score / max_possible * 100) if max_possible > 0 else 0
    conn.close()
    return render_template('my_grades.html', student=student, task_grades=task_grades, project_grades=project_grades, total_score=total_score, total_task_score=total_task_score, total_project_score=total_project_score, avg_percent=round(avg_percent, 1))

@app.route('/notifications')
def notifications():
    if 'student_id' not in session:
        return redirect(url_for('login_student'))
    conn = get_db()
    notifs = conn.execute("SELECT * FROM notifications WHERE student_id = ? ORDER BY created_at DESC", (session['student_id'],)).fetchall()
    conn.execute("UPDATE notifications SET is_read = 1 WHERE student_id = ?", (session['student_id'],))
    conn.commit()
    conn.close()
    return render_template('notifications.html', notifications=notifs)

@app.route('/certificate')
def certificate():
    if 'student_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('login_student'))
    conn = get_db()
    student = conn.execute("SELECT * FROM students WHERE id = ?", (session['student_id'],)).fetchone()
    progress = conn.execute("SELECT COUNT(*) as completed, (SELECT COUNT(*) FROM tasks) as total FROM student_progress WHERE student_id = ? AND completed = 1", (session['student_id'],)).fetchone()
    progress_percent = (progress['completed'] / progress['total'] * 100) if progress['total'] > 0 else 0
    project_count = conn.execute("SELECT COUNT(*) FROM project_submissions WHERE student_id = ? AND status = 'graded'", (session['student_id'],)).fetchone()[0]
    total_projects = conn.execute("SELECT COUNT(*) FROM practical_projects").fetchone()[0]
    project_percent = (project_count / total_projects * 100) if total_projects > 0 else 0
    overall_progress = (progress_percent + project_percent) / 2
    badges = conn.execute("SELECT * FROM badges WHERE student_id = ?", (session['student_id'],)).fetchall()
    cert = conn.execute("SELECT * FROM certificates WHERE student_id = ?", (session['student_id'],)).fetchone()
    cert_code = None
    if overall_progress >= 80:
        if not cert:
            cert_code = f"BL3D-{session['student_id']}-{datetime.now().strftime('%Y%m%d')}"
            conn.execute("INSERT INTO certificates (student_id, certificate_code) VALUES (?, ?)", (session['student_id'], cert_code))
            conn.commit()
        else:
            cert_code = cert['certificate_code']
    conn.close()
    return render_template('certificate.html', student=student, progress=overall_progress, badges=badges, now=datetime.now(), cert_code=cert_code, task_progress=progress_percent, project_progress=project_percent)

@app.route('/api/stats')
def api_stats():
    try:
        conn = get_db()
        today = datetime.now().strftime('%Y-%m-%d')
        last_week = (datetime.now() - timedelta(days=7)).strftime('%Y-%m-%d')
        teachers = conn.execute("SELECT COUNT(*) as count FROM teachers").fetchone()['count']
        students = conn.execute("SELECT COUNT(*) as count FROM students").fetchone()['count']
        total = teachers + students
        new_teachers_today = conn.execute("SELECT COUNT(*) as count FROM teachers WHERE DATE(created_at) = ?", (today,)).fetchone()['count']
        new_students_today = conn.execute("SELECT COUNT(*) as count FROM students WHERE DATE(created_at) = ?", (today,)).fetchone()['count']
        teachers_last_week = conn.execute("SELECT COUNT(*) as count FROM teachers WHERE DATE(created_at) >= ?", (last_week,)).fetchone()['count']
        students_last_week = conn.execute("SELECT COUNT(*) as count FROM students WHERE DATE(created_at) >= ?", (last_week,)).fetchone()['count']
        growth_percent = 0
        if total > 0:
            growth_percent = round(((teachers_last_week + students_last_week) / total) * 100, 1)
        conn.close()
        return jsonify({'success': True, 'teachers': teachers, 'students': students, 'total': total, 'new_teachers_today': new_teachers_today, 'new_students_today': new_students_today, 'growth_percent': growth_percent, 'last_updated': datetime.now().strftime('%H:%M:%S')})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e), 'teachers': 0, 'students': 0}), 500

@app.route('/api/chat', methods=['POST'])
def api_chat():
    data = request.get_json()
    message = data.get('message', '')
    user_id = session.get('student_id') or session.get('teacher_id') or 0
    user_type = session.get('user_type', 'guest')
    responses = {
        'сәлем': 'Сәлеметсіз бе! Мен Blender 3D көмекшісімін. 🎨',
        'blender': 'Blender — ашық бастапқы коды бар 3D бағдарлама.',
        'блендер': 'Blender — тегін 3D бағдарлама. blender.org',
        'сертификат': 'Сертификат алу үшін 80% прогреске жету керек.',
        'xp': 'XP ұпайларын тапсырмаларды орындап жинаңыз.',
        'leaderboard': 'Leaderboard-та топ оқушылар көрсетілген. 🏆',
        'бейдж': 'Бейдждер XP жинаған сайын беріледі.',
        'практика': 'Әр тақырыптан кейін практикалық жобаны орындаңыз.',
        'файл': 'Практикалық жобаңызды .blend, .pdf, .pptx форматында жүктеңіз.',
        'тақырыптар': 'Бізде 7 тақырып бар.',
        'қалай бастау': 'Оқушы ретінде тіркеліңіз, тақырыптарды ретпен оқыңыз! 🚀',
    }
    response = 'Кешіріңіз, бұл сұраққа нақты жауап бере алмаймын. Қай тақырып туралы сұрақ?'
    message_lower = message.lower()
    for key, resp in responses.items():
        if key in message_lower:
            response = resp
            break
    conn = get_db()
    conn.execute("INSERT INTO chat_messages (user_id, user_type, message, response) VALUES (?, ?, ?, ?)", (user_id, user_type, message, response))
    conn.commit()
    conn.close()
    return jsonify({'response': response})

@app.route('/practice')
def practice():
    if 'student_id' not in session or session.get('user_type') != 'student':
        return redirect(url_for('login_student'))
    conn = get_db()
    tasks = conn.execute("SELECT t.*, tp.title as topic_title FROM tasks t JOIN topics tp ON t.topic_id = tp.id ORDER BY tp.order_num, t.order_num").fetchall()
    progress_data = conn.execute("SELECT COUNT(*) as completed, (SELECT COUNT(*) FROM tasks) as total, COALESCE(SUM(score), 0) as total_xp FROM student_progress WHERE student_id = ? AND completed = 1", (session['student_id'],)).fetchone()
    progress = (progress_data['completed'] / progress_data['total'] * 100) if progress_data['total'] > 0 else 0
    task_progress = {}
    for task in tasks:
        prog = conn.execute("SELECT * FROM student_progress WHERE student_id = ? AND task_id = ?", (session['student_id'], task['id'])).fetchone()
        task_progress[task['id']] = prog
    conn.close()
    return render_template('practice.html', tasks=tasks, task_progress=task_progress, progress=progress, completed_count=progress_data['completed'], total_tasks=progress_data['total'], total_xp=progress_data['total_xp'])

@app.route('/save_student_project', methods=['POST'])
def save_student_project():
    if 'student_id' not in session:
        return jsonify({'error': 'Unauthorized'}), 401
    project_id = request.form.get('project_id')
    title = request.form.get('title')
    description = request.form.get('description', '')
    tools = request.form.get('tools', '')
    if not title:
        return jsonify({'error': 'Жоба атауын енгізіңіз'}), 400
    conn = get_db()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS student_projects (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            project_id INTEGER NOT NULL,
            title TEXT NOT NULL,
            description TEXT,
            tools TEXT,
            screenshot1 TEXT,
            screenshot2 TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (student_id) REFERENCES students(id),
            FOREIGN KEY (project_id) REFERENCES practical_projects(id)
        )
    """)
    screenshot1_path = None
    screenshot2_path = None
    if 'screenshot1' in request.files:
        file = request.files['screenshot1']
        if file.filename:
            filename = f"student_{session['student_id']}_proj_{project_id}_sc1_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            screenshot1_path = filename
    if 'screenshot2' in request.files:
        file = request.files['screenshot2']
        if file.filename:
            filename = f"student_{session['student_id']}_proj_{project_id}_sc2_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            screenshot2_path = filename
    conn.execute("INSERT INTO student_projects (student_id, project_id, title, description, tools, screenshot1, screenshot2) VALUES (?, ?, ?, ?, ?, ?, ?)", (session['student_id'], project_id, title, description, tools, screenshot1_path, screenshot2_path))
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'message': 'Жоба сәтті сақталды!'})

@app.route('/faq')
def faq_page():
    return render_template('faq.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)