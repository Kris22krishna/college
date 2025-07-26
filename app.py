
import os
import random
from flask import Flask, render_template, request, redirect, url_for, Response
import gspread
from oauth2client.service_account import ServiceAccountCredentials
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
from datetime import datetime

# ---------------- GOOGLE SHEETS SETUP ---------------- #
def init_google_sheets():
    scope = [
        "https://spreadsheets.google.com/feeds",
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive.file",
        "https://www.googleapis.com/auth/drive"
    ]
    creds = ServiceAccountCredentials.from_json_keyfile_name("service_account.json", scope)
    client = gspread.authorize(creds)
    sheet = client.open("Math Quiz Results").sheet1

    if not sheet.row_values(1):
        sheet.insert_row(["Name", "Question", "User Answer", "Correct Answer", "Status", "Timestamp"], 1)
    return sheet

sheet = init_google_sheets()

# ---------------- QUIZ LOGIC ---------------- #
def generate_question():
    num1, num2 = random.randint(1, 20), random.randint(1, 10)
    op = random.choice(['+', '-', '*', '/'])
    if op == '/':
        num1 = num1 * num2
        correct_answer = num1 // num2
    else:
        correct_answer = eval(f"{num1}{op}{num2}")
    return f"{num1} {op} {num2}", correct_answer

def check_answer(user_answer, correct_answer):
    try:
        return int(user_answer) == correct_answer
    except:
        return False

def save_to_google_sheet(name, questions):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    for q in questions:
        sheet.append_row([name, q['question'], q['user_answer'], q['correct_answer'], q['status'], timestamp])

# ---------------- FLASK APP ---------------- #
app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/quiz', methods=['GET', 'POST'])
def quiz():
    if request.method == 'POST':
        name = request.form.get('name')
        total_questions = 5
        questions = []
        score = 0

        # Retrieve the original questions from hidden fields
        for i in range(total_questions):
            question = request.form.get(f'question{i}')
            correct_answer = eval(question.replace("/", "//"))  # Safe evaluation
            user_ans = request.form.get(f'answer{i}', '')
            is_correct = check_answer(user_ans, correct_answer)
            if is_correct:
                score += 1
            questions.append({
                'question': question,
                'user_answer': user_ans,
                'correct_answer': correct_answer,
                'status': "Correct" if is_correct else "Wrong"
            })

        save_to_google_sheet(name, questions)
        return redirect(url_for('results'))

    # GET request - generate quiz questions
    quiz_questions = [generate_question()[0] for _ in range(5)]
    return render_template('quiz.html', questions=quiz_questions)


@app.route('/results')
def results():
    records = sheet.get_all_records()
    df = pd.DataFrame(records)
    summary = []
    if not df.empty:
        for user in df["Name"].unique():
            user_data = df[df["Name"] == user]
            total = len(user_data)
            correct = len(user_data[user_data["Status"] == "Correct"])
            incorrect = total - correct
            summary.append((user, total, correct, incorrect))
    return render_template('results.html', summary=summary)

@app.route('/analytics')
def analytics():
    records = sheet.get_all_records()
    if not records:
        return "No data available."
    df = pd.DataFrame(records)
    if not os.path.exists(app.static_folder):
        os.makedirs(app.static_folder)
    plt.figure(figsize=(8, 5))
    sns.countplot(data=df, x="Name", hue="Status")
    chart_path = os.path.join(app.static_folder, 'analytics.png')
    plt.savefig(chart_path)
    plt.close()
    return render_template('analytics.html', chart_url='/static/analytics.png')

@app.route('/worksheet')
def worksheet():
    questions = [generate_question()[0] for _ in range(20)]
    content = "Math Worksheet\n\n"
    for i, q in enumerate(questions, start=1):
        content += f"{i}. {q} = \n"
    return Response(
        content,
        mimetype="text/plain",
        headers={"Content-disposition": "attachment; filename=worksheet.txt"}
    )

# ---------------- VERCEL HANDLER ---------------- #
def handler(event, context):
    return app

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000)
