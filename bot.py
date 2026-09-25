import os
import sqlite3
from telegram import Update
from telegram.ext import (
    Application, CommandHandler, MessageHandler,
    ConversationHandler, filters, ContextTypes
)
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4

TOKEN = os.environ.get("BOT_TOKEN")
WEBHOOK_URL = os.environ.get("WEBHOOK_URL")  # Ex: https://seu-bot.onrender.com
PORT = int(os.environ.get("PORT", 8080))

DB = "usuarios.db"
NAME, EMAIL, WAIT_PDF = range(3)

def init_db():
    conn = sqlite3.connect(DB)
    conn.execute("""CREATE TABLE IF NOT EXISTS usuarios (
        user_id INTEGER PRIMARY KEY,
        nome TEXT,
        email TEXT
    )""")
    conn.commit()
    conn.close()

def save_user(user_id, nome, email):
    conn = sqlite3.connect(DB)
    conn.execute(
        "INSERT OR REPLACE INTO usuarios (user_id, nome, email) VALUES (?, ?, ?)",
        (user_id, nome, email),
    )
    conn.commit()
    conn.close()

def get_user(user_id):
    conn = sqlite3.connect(DB)
    row = conn.execute(
        "SELECT nome, email FROM usuarios WHERE user_id = ?", (user_id,)
    ).fetchone()
    conn.close()
    return row

def criar_pdf(path, nome, email):
    c = canvas.Canvas(path, pagesize=A4)
    w, h = A4
    c.setFont("Helvetica-Bold", 18)
    c.drawString(50, h - 60, "Formulário de Cadastro")
    c.setFont("Helvetica", 12)
    c.drawString(50, h - 110, "Nome:")
    c.drawString(150, h - 110, nome)
    c.drawString(50, h - 140, "E-mail:")
    c.drawString(150, h - 140, email)
    c.drawString(50, h - 190, "Telefone:")
    c.acroForm.textfield(name="telefone", x=150, y=h - 200, width=250, height=22,
                         borderStyle="inset", forceBorder=True, fontSize=12)
    c.drawString(50, h - 240, "Endereço:")
    c.acroForm.textfield(name="endereco", x=150, y=h - 250, width=350, height=22,
                         borderStyle="inset", forceBorder=True, fontSize=12)
    c.drawString(50, h - 290, "Observações:")
    c.acroForm.textfield(name="obs", x=50, y=h - 420, width=450, height=120,
                         borderStyle="inset", forceBorder=True, fontSize=12,
                         fieldFlags="multiline")
    c.save()

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if user:
        nome, email = user
        await update.message.reply_text(
            f"Olá de novo, {nome}! 👋 Já tenho seu cadastro.\n"
            f"E-mail salvo: {email}\n\nVou te mandar o formulário novamente."
        )
        await enviar_formulario(update, context)
        return WAIT_PDF
    await update.message.reply_text(
        "Olá! 👋 Vou fazer seu cadastro rapidinho.\n\nQual é o seu *nome*?",
        parse_mode="Markdown",
    )
    return NAME

async def receber_nome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["nome"] = update.message.text.strip()
    await update.message.reply_text(
        f"Prazer, {context.user_data['nome']}! 😄\nAgora me diga seu *e-mail*:",
        parse_mode="Markdown",
    )
    return EMAIL

async def receber_email(update: Update, context: ContextTypes.DEFAULT_TYPE):
    email = update.message.text.strip()
    nome = context.user_data["nome"]
    user_id = update.effective_user.id
    save_user(user_id, nome, email)
    await update.message.reply_text(
        f"Perfeito, {nome}! Cadastro salvo com sucesso. ✅\n\n"
        "Agora vou te enviar um formulário em PDF para você preencher."
    )
    await enviar_formulario(update, context)
    return WAIT_PDF

async def enviar_formulario(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user = get_user(user_id)
    if not user:
        await update.message.reply_text("Você ainda não está cadastrado. Use /start.")
        return
    nome, email = user
    path = f"formulario_{user_id}.pdf"
    criar_pdf(path, nome, email)
    with open(path, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=f"formulario_{nome.replace(' ', '_')}.pdf",
            caption=(
                f"Prontinho, {nome}! 📄\n\n"
                "Baixe, preencha os campos (telefone, endereço, observações) "
                "e me envie o PDF de volta. Vou guardar aqui."
            ),
        )
    os.remove(path)

async def receber_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    doc = update.message.document
    user_id = update.effective_user.id
    if not doc.file_name.lower().endswith(".pdf"):
        await update.message.reply_text("Por favor, envie um arquivo PDF. 📎")
        return WAIT_PDF
    file = await doc.get_file()
    destino = f"recebido_{user_id}.pdf"
    await file.download_to_drive(destino)
    user = get_user(user_id)
    nome = user[0] if user else "amigo"
    await update.message.reply_text(
        f"Recebi seu formulário, {nome}! 🎉\n"
        f"Salvei como `{destino}`.\n\n"
        "Se quiser começar de novo, use /start."
    )
    return WAIT_PDF

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("Operação cancelada. Use /start quando quiser.")
    return ConversationHandler.END

def main():
    init_db()
    app = Application.builder().token(TOKEN).build()
    conv = ConversationHandler(
        entry_points=[CommandHandler("start", start)],
        states={
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_nome)],
            EMAIL: [MessageHandler(filters.TEXT & ~filters.COMMAND, receber_email)],
            WAIT_PDF: [MessageHandler(filters.Document.PDF, receber_pdf)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    app.add_handler(conv)
    app.run_webhook(
        listen="0.0.0.0",
        port=PORT,
        url_path="webhook",
        webhook_url=f"{WEBHOOK_URL}/webhook",
    )

if __name__ == "__main__":
    main()
