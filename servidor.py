from flask import Flask, jsonify, request, session
import os
import secrets
import sqlite3
from pathlib import Path
from werkzeug.security import check_password_hash, generate_password_hash


BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "usuarios.db"

app = Flask(__name__)
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", secrets.token_hex(32))


def get_db_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout = 10000")
    return conn


def init_db():
    with get_db_connection() as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS usuarios (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                usuario TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL
            )
            """
        )
        conn.commit()


@app.post("/registro")
def registro():
    data = request.get_json(silent=True) or {}
    usuario = data.get("usuario")
    password = data.get("contraseña")

    if not usuario or not password:
        return (
            jsonify(
                {
                    "error": 'Debe enviar JSON con {"usuario": "...", "contraseña": "..."}'
                }
            ),
            400,
        )

    password_hash = generate_password_hash(password)

    try:
        with get_db_connection() as conn:
            conn.execute(
                "INSERT INTO usuarios (usuario, password_hash) VALUES (?, ?)",
                (usuario, password_hash),
            )
            conn.commit()
    except sqlite3.IntegrityError:
        return jsonify({"error": "El nombre de usuario ya existe"}), 409
    except sqlite3.OperationalError:
        return jsonify({"error": "Base de datos ocupada. Intenta nuevamente."}), 503

    return jsonify({"mensaje": "Usuario registrado correctamente"}), 201


@app.post("/login")
def login():
    data = request.get_json(silent=True) or {}
    usuario = data.get("usuario")
    password = data.get("contraseña")

    if not usuario or not password:
        return (
            jsonify(
                {
                    "error": 'Debe enviar JSON con {"usuario": "...", "contraseña": "..."}'
                }
            ),
            400,
        )

    with get_db_connection() as conn:
        row = conn.execute(
            "SELECT id, usuario, password_hash FROM usuarios WHERE usuario = ?", (usuario,)
        ).fetchone()

    if row is None or not check_password_hash(row["password_hash"], password):
        return jsonify({"error": "Credenciales inválidas"}), 401

    session["user_id"] = row["id"]
    session["usuario"] = row["usuario"]
    return jsonify({"mensaje": "Inicio de sesión exitoso"}), 200


@app.get("/tareas")
def tareas():
    if "user_id" not in session:
        return jsonify({"error": "Debes iniciar sesión para acceder a las tareas"}), 401

    usuario = session.get("usuario", "usuario")
    html = f"""
    <!doctype html>
    <html lang="es">
    <head>
      <meta charset="utf-8">
      <title>Tareas</title>
      <style>
        body {{
          font-family: Arial, sans-serif;
          margin: 2rem;
          background: #f5f7fb;
          color: #1f2937;
        }}
        .box {{
          max-width: 680px;
          background: white;
          border-radius: 12px;
          padding: 1.5rem;
          box-shadow: 0 10px 20px rgba(0, 0, 0, 0.07);
        }}
      </style>
    </head>
    <body>
      <div class="box">
        <h1>Bienvenido/a, {usuario}</h1>
        <p>Accediste correctamente al módulo de tareas.</p>
        <ul>
          <li>Registrar usuario: <code>POST /registro</code></li>
          <li>Iniciar sesión: <code>POST /login</code></li>
          <li>Ver tareas: <code>GET /tareas</code></li>
        </ul>
      </div>
    </body>
    </html>
    """
    return html, 200, {"Content-Type": "text/html; charset=utf-8"}


if __name__ == "__main__":
    init_db()
    app.run(debug=True)
