import os
import sqlite3
from datetime import date
from urllib.parse import quote
from uuid import uuid4

from flask import Flask, flash, redirect, render_template, request, send_from_directory, session, url_for
from werkzeug.utils import secure_filename

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY", "jovens-sem-limites-2026")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, "uploads")
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

ADMIN_EMAIL = "railsonrls46@gmail.com"
ADMIN_PASSWORD = "24107266"
PIX_NUMBER = "12799559379"
PIX_NAME = "Jardson Sousa Santos"
WHATSAPP_NUMBER = "+55 (99)98433-6831"


def get_db():
    conn = sqlite3.connect("inscricoes.db")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS inscritos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT NOT NULL,
            data_nascimento TEXT,
            sexo TEXT,
            categoria TEXT,
            telefone TEXT,
            whatsapp TEXT,
            pix_num TEXT,
            pix_nome TEXT,
            comprovante TEXT,
            status TEXT DEFAULT 'pendente',
            pagamento_confirmado INTEGER DEFAULT 0,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def periodo_aberto():
    hoje = date.today()
    return 2 <= hoje.day <= 7


@app.route("/")
def index():
    return render_template(
        "index.html",
        periodo_aberto=periodo_aberto(),
        pix_number=PIX_NUMBER,
        pix_name=PIX_NAME,
        whatsapp_number=WHATSAPP_NUMBER,
    )


@app.route("/inscrever", methods=["POST"])
def inscrever():
    if not periodo_aberto():
        flash("As inscrições estão encerradas neste período.")
        return redirect(url_for("index"))

    nome = request.form.get("nome", "").strip()
    data_nascimento = request.form.get("data_nascimento", "").strip()
    sexo = request.form.get("sexo", "").strip()
    categoria = request.form.get("categoria", "").strip()
    telefone = request.form.get("telefone", "").strip()
    whatsapp = request.form.get("whatsapp", "").strip()

    if not all([nome, data_nascimento, sexo, categoria, telefone, whatsapp]):
        flash("Preencha todos os campos obrigatórios.")
        return redirect(url_for("index"))

    comprovante_arquivo = request.files.get("comprovante")
    comprovante_nome = None
    if comprovante_arquivo and comprovante_arquivo.filename:
        nome_arquivo = secure_filename(comprovante_arquivo.filename)
        extensao = os.path.splitext(nome_arquivo)[1].lower()
        if extensao not in [".jpg", ".jpeg", ".png", ".pdf"]:
            flash("Formato do comprovante inválido. Use JPG, PNG ou PDF.")
            return redirect(url_for("index"))
        comprovante_nome = f"{uuid4().hex}_{nome_arquivo}"
        comprovante_arquivo.save(os.path.join(app.config["UPLOAD_FOLDER"], comprovante_nome))

    conn = get_db()
    conn.execute(
        """
        INSERT INTO inscritos (
            nome, data_nascimento, sexo, categoria, telefone, whatsapp,
            pix_num, pix_nome, comprovante, status, pagamento_confirmado
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'pendente', 0)
        """,
        (
            nome,
            data_nascimento,
            sexo,
            categoria,
            telefone,
            whatsapp,
            PIX_NUMBER,
            PIX_NAME,
            comprovante_nome,
        ),
    )
    conn.commit()
    conn.close()

    flash("Inscrição enviada com sucesso! Aguarde a confirmação do pagamento.")
    return redirect(url_for("status"))


@app.route("/status", methods=["GET", "POST"])
def status():
    resultado = None
    termo = ""

    if request.method == "POST":
        termo = request.form.get("termo", "").strip()
        if termo:
            conn = get_db()
            resultado = conn.execute(
                """
                SELECT *
                FROM inscritos
                WHERE nome LIKE ? OR telefone LIKE ? OR whatsapp LIKE ?
                ORDER BY id DESC
                """,
                (f"%{termo}%", f"%{termo}%", f"%{termo}%"),
            ).fetchall()
            conn.close()

    return render_template("status.html", resultado=resultado, termo=termo)


@app.route("/uploads/<filename>")
def arquivo_upload(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)


@app.route("/admin")
def admin_login_page():
    if session.get("admin"):
        return redirect(url_for("admin_painel"))
    return render_template("admin_login.html")


@app.route("/admin/login", methods=["POST"])
def admin_login():
    email = request.form.get("email", "").strip()
    senha = request.form.get("senha", "").strip()

    if email == ADMIN_EMAIL and senha == ADMIN_PASSWORD:
        session["admin"] = True
        return redirect(url_for("admin_painel"))

    flash("E-mail ou senha incorretos.")
    return redirect(url_for("admin_login_page"))


@app.route("/admin/logout")
def admin_logout():
    session.pop("admin", None)
    return redirect(url_for("admin_login_page"))


@app.route("/admin/painel")
def admin_painel():
    if not session.get("admin"):
        return redirect(url_for("admin_login_page"))

    conn = get_db()
    inscritos = conn.execute("SELECT * FROM inscritos ORDER BY id DESC").fetchall()
    total = conn.execute("SELECT COUNT(*) AS total FROM inscritos").fetchone()["total"]
    aprovados = conn.execute("SELECT COUNT(*) AS total FROM inscritos WHERE status = 'aprovado'").fetchone()["total"]
    pendentes = conn.execute("SELECT COUNT(*) AS total FROM inscritos WHERE status = 'pendente'").fetchone()["total"]
    conn.close()

    return render_template(
        "admin.html",
        inscritos=inscritos,
        total=total,
        aprovados=aprovados,
        pendentes=pendentes,
    )


@app.route("/admin/aprovar/<int:id>")
def aprovar_inscricao(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login_page"))

    conn = get_db()
    conn.execute("UPDATE inscritos SET status = 'aprovado', pagamento_confirmado = 1 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_painel"))


@app.route("/admin/rejeitar/<int:id>")
def rejeitar_inscricao(id):
    if not session.get("admin"):
        return redirect(url_for("admin_login_page"))

    conn = get_db()
    conn.execute("UPDATE inscritos SET status = 'pendente', pagamento_confirmado = 0 WHERE id = ?", (id,))
    conn.commit()
    conn.close()
    return redirect(url_for("admin_painel"))


if __name__ == "__main__":
    init_db()
    app.run(host="0.0.0.0", port=5000, debug=True)

